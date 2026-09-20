from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

from edge.outbox import Outbox


LOGGER = logging.getLogger("transitnexus.uplink")

DEFAULT_BACKEND_URL = "https://transitnexus-v3.onrender.com"
HEARTBEAT_INTERVAL_S = 2.0
REQUEST_TIMEOUT_S = 10.0
MAX_BACKOFF_S = 30.0


@dataclass
class HeartbeatState:
    bus_id: str
    lat: float
    lon: float
    accuracy_m: float
    speed_kmh: float
    heading: float
    ts: str
    camera: bool
    gps: bool
    ai_fps: float
    queue_depth: int


class UplinkWorker:
    """Background event uploader and latest-state heartbeat sender."""

    def __init__(
        self,
        *,
        bus_id: str,
        api_key: str,
        backend_url: str = DEFAULT_BACKEND_URL,
        outbox: Optional[Outbox] = None,
    ) -> None:
        self.bus_id = bus_id
        self.api_key = api_key
        self.backend_url = backend_url.rstrip("/")
        self.outbox = outbox or Outbox()

        self._stop_event = threading.Event()
        self._heartbeat_lock = threading.Lock()
        self._heartbeat: Optional[HeartbeatState] = None

        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": self.api_key})

        self._event_thread = threading.Thread(
            target=self._event_loop,
            name=f"uplink-events-{bus_id}",
            daemon=True,
        )
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"uplink-heartbeat-{bus_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._event_thread.start()
        self._heartbeat_thread.start()

    def stop(self, timeout_s: float = 3.0) -> None:
        self._stop_event.set()
        self._event_thread.join(timeout=timeout_s)
        self._heartbeat_thread.join(timeout=timeout_s)
        self._session.close()

    def enqueue_event(self, event_id: str, payload: dict) -> bool:
        """Durably persist an event before any network attempt."""
        inserted = self.outbox.enqueue(event_id, payload)

        if inserted:
            LOGGER.info(
                "queued event bus=%s event_id=%s queue_depth=%d",
                self.bus_id,
                event_id,
                self.outbox.count(),
            )

        return inserted

    def update_heartbeat(
        self,
        *,
        lat: float,
        lon: float,
        accuracy_m: float,
        speed_kmh: float,
        heading: float,
        ts: str,
        camera: bool,
        gps: bool,
        ai_fps: float,
    ) -> None:
        """Replace the latest heartbeat state; no heartbeat queue is created."""
        state = HeartbeatState(
            bus_id=self.bus_id,
            lat=float(lat),
            lon=float(lon),
            accuracy_m=float(accuracy_m),
            speed_kmh=float(speed_kmh),
            heading=float(heading),
            ts=ts,
            camera=bool(camera),
            gps=bool(gps),
            ai_fps=float(ai_fps),
            queue_depth=self.outbox.count(),
        )

        with self._heartbeat_lock:
            self._heartbeat = state

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    def _event_loop(self) -> None:
        backoff_s = 1.0

        while not self._stop_event.is_set():
            row = self.outbox.oldest()

            if row is None:
                self._stop_event.wait(0.5)
                continue

            try:
                response = self._session.post(
                    f"{self.backend_url}/v1/events",
                    headers=self._headers(),
                    json=row.payload,
                    timeout=REQUEST_TIMEOUT_S,
                )

                if 200 <= response.status_code < 300:
                    self.outbox.delete(row.event_id)
                    backoff_s = 1.0
                    LOGGER.info(
                        "event delivered bus=%s event_id=%s",
                        self.bus_id,
                        row.event_id,
                    )
                    continue

                if 400 <= response.status_code < 500:
                    self.outbox.delete(row.event_id)
                    LOGGER.error(
                        "event rejected bus=%s event_id=%s status=%d",
                        self.bus_id,
                        row.event_id,
                        response.status_code,
                    )
                    backoff_s = 1.0
                    continue

                LOGGER.warning(
                    "event upload server error bus=%s event_id=%s status=%d "
                    "retry_in=%.1fs",
                    self.bus_id,
                    row.event_id,
                    response.status_code,
                    backoff_s,
                )

            except requests.RequestException as exc:
                LOGGER.warning(
                    "event upload network error bus=%s event_id=%s "
                    "retry_in=%.1fs error=%s",
                    self.bus_id,
                    row.event_id,
                    backoff_s,
                    type(exc).__name__,
                )

            self._stop_event.wait(backoff_s)
            backoff_s = min(backoff_s * 2.0, MAX_BACKOFF_S)

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._heartbeat_lock:
                state = self._heartbeat

            if state is not None:
                self._send_heartbeat(state)

            self._stop_event.wait(HEARTBEAT_INTERVAL_S)

    def _send_heartbeat(self, state: HeartbeatState) -> None:
        payload = {
            "bus_id": state.bus_id,
            "lat": state.lat,
            "lon": state.lon,
            "accuracy_m": state.accuracy_m,
            "speed_kmh": state.speed_kmh,
            "heading": state.heading,
            "ts": state.ts,
            "status": {
                "camera": state.camera,
                "gps": state.gps,
                "ai_fps": state.ai_fps,
                "queue_depth": state.queue_depth,
            },
        }

        try:
            response = self._session.post(
                f"{self.backend_url}/v1/heartbeat",
                headers=self._headers(),
                json=payload,
                timeout=REQUEST_TIMEOUT_S,
            )

            if response.status_code >= 400:
                LOGGER.warning(
                    "heartbeat rejected bus=%s status=%d",
                    self.bus_id,
                    response.status_code,
                )

        except requests.RequestException as exc:
            LOGGER.warning(
                "heartbeat network error bus=%s error=%s",
                self.bus_id,
                type(exc).__name__,
            )
