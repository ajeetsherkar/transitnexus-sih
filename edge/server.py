from __future__ import annotations

import json
import os
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
from edge.events import EventEngine


BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_FILE = BASE_DIR / "edge" / "static" / "client.html"

app = FastAPI(
    title="TransitNexus Edge Streaming Server",
    description="Round 3 phone camera streaming and edge inference service.",
    version="3.0.0",
)


def authenticate_bus(bus_id: str, api_key: str) -> bool:
    """Validate a phone's bus ID and API key against the existing Bus table."""
    if not bus_id or not api_key:
        return False

    from sqlalchemy.orm import Session

    with Session(engine) as db:
        bus = db.execute(
            select(Bus).where(
                Bus.bus_id == bus_id,
                Bus.api_key_hash == hash_api_key(api_key),
            )
        ).scalar_one_or_none()

        return bus is not None


def to_boxes(detections: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten detector output into the phone overlay format."""
    boxes: list[dict[str, Any]] = []

    for group in ("potholes", "objects"):
        for detection in detections.get(group, []):
            boxes.append(
                {
                    "label": detection["label"],
                    "confidence": round(float(detection["confidence"]), 4),
                    "bbox": [
                        round(float(value), 2)
                        for value in detection["bbox"]
                    ],
                    "track_id": detection.get("track_id"),
                }
            )

    return boxes


def process_frame(
    detector: Detector,
    event_engine: EventEngine,
    frame: np.ndarray,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Run one frame through the per-phone detector and event engine.

    Event persistence/upload is intentionally deferred to A4.
    """
    detections = detector.detect(frame)

    timestamp_s = float(metadata.get("t_capture", 0)) / 1000.0
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

    # A4 will persist/upload these events. For A3 we only expose
    # the count/type as part of the WebSocket response.
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
        "gps": {
            "lat": metadata.get("lat"),
            "lon": metadata.get("lon"),
            "accuracy_m": metadata.get("acc"),
        },
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
    return JSONResponse({"status": "ok", "service": "edge-streaming"})


@app.websocket("/ws/stream")
async def stream(websocket: WebSocket) -> None:
    """
    Per-phone WebSocket stream.

    Each connection gets its own Detector and EventEngine, preserving
    independent ByteTrack and event state.
    """
    bus_id = websocket.query_params.get("bus_id", "")
    api_key = websocket.query_params.get("key", "")

    await websocket.accept()

    if not authenticate_bus(bus_id, api_key):
        await websocket.close(code=1008, reason="Invalid bus credentials")
        return

    detector = Detector()
    event_engine = EventEngine()
    metadata: dict[str, Any] | None = None

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
                    {"error": "Frame metadata must arrive before JPEG bytes"}
                )
                continue

            frame_array = np.frombuffer(binary, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is None:
                await websocket.send_json(
                    {"error": "Invalid JPEG frame"}
                )
                metadata = None
                continue

            result = await run_in_threadpool(
                process_frame,
                detector,
                event_engine,
                frame,
                metadata,
            )

            await websocket.send_json(
                {
                    "boxes": result["boxes"],
                    "events": result["events"],
                    "gps": result["gps"],
                    "server_ts": datetime.now(timezone.utc).isoformat(),
                }
            )

            metadata = None

    except WebSocketDisconnect:
        pass
    finally:
        # Drop references to the per-phone detector/event state.
        detector = None  # type: ignore[assignment]
        event_engine = None  # type: ignore[assignment]
