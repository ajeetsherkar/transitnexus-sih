from pathlib import Path

import json

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent.parent

EVENTS_FILE = BASE_DIR / "data" / "processed" / "events.json"


app = FastAPI(
    title="TransitNexus API",
    description="API for serving urban mobility events and congestion heatmap data.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Connected WebSocket clients for real-time incident alerts.
connected_clients: set[WebSocket] = set()


def load_events():
    """Load the latest events from events.json."""
    if not EVENTS_FILE.exists():
        return []

    with open(EVENTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


async def broadcast_incident(event: dict):
    """Broadcast a new incident event to all connected WebSocket clients."""
    disconnected_clients = set()

    message = {
        "type": "incident",
        "event": event,
    }

    for websocket in connected_clients:
        try:
            await websocket.send_json(message)
        except Exception:
            disconnected_clients.add(websocket)

    connected_clients.difference_update(disconnected_clients)


@app.get("/")
def root():
    return {
        "project": "TransitNexus",
        "status": "running",
        "endpoints": [
            "/events",
            "/heatmap-data",
            "/ws/alerts",
            "/docs",
        ],
    }


@app.get("/events")
def get_events(
    type: str | None = Query(
        default=None,
        description="Filter events by event type, e.g. pothole, car, congestion",
    )
):
    """Return all events or filter them by event type."""
    events = load_events()

    if type is not None:
        events = [
            event
            for event in events
            if event.get("event_type") == type
        ]

    return events


@app.get("/heatmap-data")
def get_heatmap_data():
    """Return congestion events grouped by rounded latitude/longitude."""
    events = load_events()

    grouped = {}

    for event in events:
        if event.get("event_type") != "congestion":
            continue

        lat = round(float(event["lat"]), 4)
        lon = round(float(event["lon"]), 4)

        key = (lat, lon)

        if key not in grouped:
            grouped[key] = {
                "lat": lat,
                "lon": lon,
                "count": 0,
            }

        grouped[key]["count"] += 1

    return list(grouped.values())


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Maintain a live WebSocket connection for real-time incident alerts."""
    await websocket.accept()
    connected_clients.add(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception:
        connected_clients.discard(websocket)


@app.post("/test/broadcast-incident")
async def test_broadcast_incident():
    """
    Local development endpoint used to verify WebSocket broadcasting.

    This does not modify events.json.
    """
    test_event = {
        "event_type": "incident",
        "confidence": 0.99,
        "lat": 19.9021,
        "lon": 74.4944,
        "timestamp": "test",
        "frame_path": "test/websocket_alert.jpg",
        "plate": "TEST-WS-01",
        "plate_source": "websocket_test",
        "plate_confidence": 0.99,
    }

    await broadcast_incident(test_event)

    return {
        "status": "broadcast_sent",
        "event": test_event,
        "connected_clients": len(connected_clients),
    }
