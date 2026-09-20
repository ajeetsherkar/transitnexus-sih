from __future__ import annotations

import argparse
import base64
import csv
import json
import logging
import os
import time
import uuid

from datetime import datetime, timezone

from pathlib import Path

from typing import Any

import cv2

import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from fastapi.concurrency import run_in_threadpool

from fastapi.responses import FileResponse, JSONResponse

from sqlalchemy import select

from backend.auth import hash_api_key

from backend.db import engine

from backend.models import Bus

from edge.detector import Detector

from edge.events import EventEngine, blur_person_heads

from edge.outbox import Outbox

from edge.uplink import UplinkWorker


LOGGER = logging.getLogger("transitnexus.edge")

BASE_DIR = Path(__file__).resolve().parent.parent

CLIENT_FILE = BASE_DIR / "edge" / "static" / "client.html"

BACKEND_URL = os.getenv(
    "TRANSITNEXUS_BACKEND_URL",
    "https://transitnexus-v3.onrender.com",
)

MAX_EVIDENCE_BYTES = 100_000
FIELD_RECORD_DIR = BASE_DIR / "data" / "field1"
RECORD_FIELD_TEST = False


class FieldRecorder:
    """Record raw edge frames and GPS metadata for A5 field testing."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.video_path = self.output_dir / "video.mp4"
        self.gps_path = self.output_dir / "gps.csv"
        self.video_writer: cv2.VideoWriter | None = None
        self.gps_file = self.gps_path.open(
            "w",
            newline="",
            encoding="utf-8",
        )
        self.gps_writer = csv.writer(self.gps_file)
        self.gps_writer.writerow(
            [
                "t_capture",
                "timestamp_utc",
                "lat",
                "lon",
                "accuracy_m",
                "speed_mps",
                "heading_deg",
            ]
        )
        self.gps_file.flush()

    def write(
        self,
        frame: np.ndarray,
        metadata: dict[str, Any],
    ) -> None:
        if self.video_writer is None:
            height, width = frame.shape[:2]
            self.video_writer = cv2.VideoWriter(
                str(self.video_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                15.0,
                (width, height),
            )
            if not self.video_writer.isOpened():
                raise RuntimeError(
                    f"Failed to open field video: {self.video_path}"
                )

        self.video_writer.write(frame)

        t_capture = metadata.get("t_capture")
        try:
            t_capture_ms = int(t_capture)
            timestamp_utc = datetime.fromtimestamp(
                t_capture_ms / 1000.0,
                tz=timezone.utc,
            ).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OSError):
            t_capture_ms = ""
            timestamp_utc = ""

        self.gps_writer.writerow(
            [
                t_capture_ms,
                timestamp_utc,
                metadata.get("lat", ""),
                metadata.get("lon", ""),
                metadata.get("acc", ""),
                metadata.get("speed", ""),
                metadata.get("heading", ""),
            ]
        )
        self.gps_file.flush()

    def close(self) -> None:
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        if not self.gps_file.closed:
            self.gps_file.flush()
            self.gps_file.close()

app = FastAPI(
    title="TransitNexus Edge Streaming Server",
    description="Round 3 phone camera streaming and edge inference service.",
    version="3.0.0",
)


def get_authenticated_bus(
    bus_id: str,
    api_key: str,
) -> Bus | None:
    """Return the local bus record when the supplied credentials are valid."""
    if not bus_id or not api_key:
        return None

    from sqlalchemy.orm import Session

    with Session(engine) as db:
        return db.execute(
            select(Bus).where(
                Bus.bus_id == bus_id,
                Bus.api_key_hash == hash_api_key(api_key),
            )
        ).scalar_one_or_none()


def authenticate_bus(bus_id: str, api_key: str) -> bool:
    """Validate a phone's bus ID and API key against the existing Bus table."""
    return get_authenticated_bus(bus_id, api_key) is not None


def to_boxes(
    detections: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Flatten detector output into the phone overlay format."""
    boxes: list[dict[str, Any]] = []

    for group in ("potholes", "objects"):
        for detection in detections.get(group, []):
            boxes.append(
                {
                    "label": detection["label"],
                    "confidence": round(
                        float(detection["confidence"]),
                        4,
                    ),
                    "bbox": [
                        round(float(value), 2)
                        for value in detection["bbox"]
                    ],
                    "track_id": detection.get("track_id"),
                }
            )

    return boxes


def encode_evidence(
    frame: np.ndarray,
    person_detections: list[dict[str, Any]],
) -> bytes:
    """Blur person heads and encode a compact JPEG evidence image."""
    evidence = frame.copy()

    blur_person_heads(
        evidence,
        person_detections,
    )

    height, width = evidence.shape[:2]

    target_width = 480

    if width > target_width:
        target_height = max(
            1,
            round(height * target_width / width),
        )
        evidence = cv2.resize(
            evidence,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )

    quality = 60

    while quality >= 25:
        success, encoded = cv2.imencode(
            ".jpg",
            evidence,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                quality,
            ],
        )

        if not success:
            raise RuntimeError("Failed to encode evidence JPEG")

        data = encoded.tobytes()

        if len(data) <= MAX_EVIDENCE_BYTES:
            return data

        quality -= 5

    # A very busy image can still exceed 100 KB at quality 25.
    # Resize once more before giving up.
    height, width = evidence.shape[:2]

    reduced_width = max(240, width // 2)

    if width > reduced_width:
        reduced_height = max(
            1,
            round(height * reduced_width / width),
        )
        evidence = cv2.resize(
            evidence,
            (reduced_width, reduced_height),
            interpolation=cv2.INTER_AREA,
        )

    success, encoded = cv2.imencode(
        ".jpg",
        evidence,
        [
            cv2.IMWRITE_JPEG_QUALITY,
            20,
        ],
    )

    if not success:
        raise RuntimeError("Failed to encode reduced evidence JPEG")

    data = encoded.tobytes()

    if len(data) > MAX_EVIDENCE_BYTES:
        raise RuntimeError("Evidence JPEG exceeds 100 KB limit")

    return data


def event_timestamp(event: dict[str, Any]) -> str:
    timestamp_s = float(event.get("timestamp_s", 0.0))

    if timestamp_s > 0:
        return datetime.fromtimestamp(
            timestamp_s,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z")

    return datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def build_uplink_event(
    event: dict[str, Any],
    *,
    bus: Bus,
    metadata: dict[str, Any],
    evidence: bytes,
) -> dict[str, Any]:
    """Convert an edge EventEngine event into the backend EventIn schema."""
    speed_mps = metadata.get("speed")

    try:
        speed_kmh = float(speed_mps) * 3.6
    except (TypeError, ValueError):
        speed_kmh = 0.0

    heading = metadata.get("heading")

    try:
        heading = float(heading) if heading is not None else 0.0
    except (TypeError, ValueError):
        heading = 0.0

    accuracy = metadata.get("acc")

    try:
        accuracy_m = float(accuracy)
    except (TypeError, ValueError):
        accuracy_m = 999.0

    lat = metadata.get("lat")
    lon = metadata.get("lon")

    if lat is None or lon is None:
        raise ValueError("Event cannot be uploaded without GPS coordinates")

    evidence_b64 = base64.b64encode(evidence).decode("ascii")

    return {
        "event_id": str(uuid.uuid4()),
        "bus_id": bus.bus_id,
        "camera_id": bus.camera_id,
        "route_id": bus.route_id,
        "type": event["event_type"],
        "confidence": float(event["confidence"]),
        "severity": event.get("severity", "medium"),
        "lat": float(lat),
        "lon": float(lon),
        "accuracy_m": accuracy_m,
        "speed_kmh": speed_kmh,
        "heading": heading,
        "ts": event_timestamp(event),
        "source": "live",
        "evidence_b64": evidence_b64,
    }


def process_frame(
    detector: Detector,
    event_engine: EventEngine,
    frame: np.ndarray,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Run one frame through detection, events and edge uplink preparation."""
    detections = detector.detect(frame)

    timestamp_s = float(
        metadata.get("t_capture", 0)
    ) / 1000.0

    speed_kmh = metadata.get("speed")

    if speed_kmh is None:
        speed_kmh = 0.0

    try:
        # Browser Geolocation API reports speed in m/s.
        # EventEngine expects speed in km/h.
        speed_kmh = float(speed_kmh) * 3.6
    except (TypeError, ValueError):
        speed_kmh = 0.0

    pothole_events = event_engine.update_potholes(
        detections["potholes"],
        frame,
        timestamp_s,
    )

    pedestrian_events = event_engine.update_pedestrians(
        detections["objects"],
        frame,
        timestamp_s,
        speed_kmh,
    )

    events = []

    for event in pothole_events:
        events.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "track_id": event["track_id"],
                "confidence": event["confidence"],
                "severity": event["severity"],
            }
        )

    for event in pedestrian_events:
        events.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "track_id": event["track_id"],
                "confidence": event["confidence"],
                "speed_kmh": event["speed_kmh"],
            }
        )

    return {
        "boxes": to_boxes(detections),
        "events": events,
        "raw_events": pothole_events + pedestrian_events,
        "person_detections": detections["objects"],
        "gps": {
            "lat": metadata.get("lat"),
            "lon": metadata.get("lon"),
            "accuracy_m": metadata.get("acc"),
        },
        "speed_kmh": speed_kmh,
        "heading": metadata.get("heading"),
    }


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "project": "TransitNexus",
            "service": "edge-streaming",
            "status": "running",
            "version": "3.0.0",
            "client": "/client",
            "websocket": "/ws/stream",
        }
    )


@app.get("/client")
async def client() -> FileResponse:
    if not CLIENT_FILE.exists():
        return FileResponse(
            path=CLIENT_FILE,
            status_code=404,
        )

    return FileResponse(
        CLIENT_FILE,
        media_type="text/html",
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "service": "edge-streaming",
        }
    )


@app.websocket("/ws/stream")
async def stream(websocket: WebSocket) -> None:
    """
    Per-phone WebSocket stream.

    Each connection gets its own Detector, EventEngine and UplinkWorker,
    preserving independent inference/tracking/uplink state.
    """
    bus_id = websocket.query_params.get("bus_id", "")
    api_key = websocket.query_params.get("key", "")

    await websocket.accept()

    bus = get_authenticated_bus(
        bus_id,
        api_key,
    )

    if bus is None:
        await websocket.close(
            code=1008,
            reason="Invalid bus credentials",
        )
        return

    detector = Detector()
    event_engine = EventEngine()

    outbox_path = Path(
        os.getenv(
            "TRANSITNEXUS_OUTBOX_DB",
            str(BASE_DIR / "edge" / "outbox.db"),
        )
    )

    outbox = Outbox(outbox_path)

    uplink = UplinkWorker(
        bus_id=bus.bus_id,
        api_key=api_key,
        backend_url=BACKEND_URL,
        outbox=outbox,
    )

    uplink.start()

    recorder = FieldRecorder(FIELD_RECORD_DIR) if RECORD_FIELD_TEST else None

    metadata: dict[str, Any] | None = None

    frame_count = 0
    fps_started = time.monotonic()

    try:
        while True:
            message = await websocket.receive()


            if message.get("type") == "websocket.disconnect":
                break

            text = message.get("text")
            binary = message.get("bytes")

            if text is not None:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"error": "Invalid metadata JSON"}
                    )
                    continue

                if not isinstance(parsed, dict):
                    await websocket.send_json(
                        {"error": "Metadata must be a JSON object"}
                    )
                    continue

                metadata = parsed
                continue

            if binary is None:
                continue

            if metadata is None:
                await websocket.send_json(
                    {
                        "error": (
                            "Frame metadata must arrive before JPEG bytes"
                        )
                    }
                )
                continue

            frame_array = np.frombuffer(
                binary,
                dtype=np.uint8,
            )

            frame = cv2.imdecode(
                frame_array,
                cv2.IMREAD_COLOR,
            )

            if frame is None:
                await websocket.send_json(
                    {"error": "Invalid JPEG frame"}
                )
                metadata = None
                continue

            if recorder is not None:
                try:
                    recorder.write(frame, metadata)
                except Exception:
                    LOGGER.exception(
                        "field recording write failed bus=%s",
                        bus.bus_id,
                    )

            processing_started = time.perf_counter()
            result = await run_in_threadpool(
                process_frame,
                detector,
                event_engine,
                frame,
                metadata,
            )
            edge_processing_ms = (
                time.perf_counter() - processing_started
            ) * 1000.0

            frame_count += 1
            elapsed = time.monotonic() - fps_started

            if elapsed >= 1.0:
                ai_fps = frame_count / elapsed
                frame_count = 0
                fps_started = time.monotonic()
            else:
                ai_fps = 0.0

            lat = result["gps"]["lat"]
            lon = result["gps"]["lon"]
            accuracy = result["gps"]["accuracy_m"]

            gps_ready = (
                lat is not None
                and lon is not None
                and accuracy is not None
            )

            if gps_ready:
                for event in result["raw_events"]:
                    try:
                        evidence = encode_evidence(
                            event["frame"],
                            result["person_detections"],
                        )

                        payload = build_uplink_event(
                            event,
                            bus=bus,
                            metadata=metadata,
                            evidence=evidence,
                        )

                        uplink.enqueue_event(
                            payload["event_id"],
                            payload,
                        )

                    except Exception as exc:
                        LOGGER.exception(
                            "failed to queue event bus=%s error=%s",
                            bus.bus_id,
                            type(exc).__name__,
                        )

                try:
                    uplink.update_heartbeat(
                        lat=float(lat),
                        lon=float(lon),
                        accuracy_m=float(accuracy),
                        speed_kmh=float(result["speed_kmh"]),
                        heading=float(result["heading"] or 0.0),
                        ts=datetime.now(
                            timezone.utc
                        ).isoformat().replace("+00:00", "Z"),
                        camera=True,
                        gps=True,
                        ai_fps=ai_fps,
                    )
                except (TypeError, ValueError):
                    pass

            await websocket.send_json(
                {
                    "boxes": result["boxes"],
                    "events": result["events"],
                    "gps": result["gps"],
                    "edge_processing_ms": round(
                        edge_processing_ms,
                        2,
                    ),
                    "server_ts": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            )

            metadata = None

    except WebSocketDisconnect:
        pass

    finally:
        if recorder is not None:
            recorder.close()
        uplink.stop()

        # Drop references to the per-phone detector/event state.
        detector = None  # type: ignore[assignment]
        event_engine = None  # type: ignore[assignment]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TransitNexus edge streaming server"
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record field-test video and GPS to data/field1/",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port",
    )
    args = parser.parse_args()

    global RECORD_FIELD_TEST
    RECORD_FIELD_TEST = args.record

    import uvicorn

    uvicorn.run(
        "edge.server:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
