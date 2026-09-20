from pathlib import Path

import json

import joblib
import pandas as pd

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent.parent

EVENTS_FILE = BASE_DIR / "data" / "processed" / "events.json"
ML_FEATURES_FILE = BASE_DIR / "data" / "processed" / "ml" / "ml_features.csv"
RF_MODEL_FILE = BASE_DIR / "models" / "congestion_rf.joblib"
GBR_MODEL_FILE = BASE_DIR / "models" / "route_delay_gbr.joblib"


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


CONTROL_CENTER_DIR = BASE_DIR / "dashboard" / "control-center"
app.mount(
    "/dashboard",
    StaticFiles(directory=CONTROL_CENTER_DIR, html=True),
    name="control-center",
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


@app.get("/zone-summary")
def get_zone_summary():
    """Return 15-minute spatial summaries for observed fleet zones."""
    events = load_events()

    if not events:
        return []

    vehicle_types = {"car", "bus", "truck", "motorcycle", "bicycle"}

    # Use elapsed time from the first event so the prototype's
    # video-relative timestamps can still be grouped temporally.
    timestamps = [
        pd.Timestamp(event["timestamp"])
        for event in events
        if event.get("timestamp")
    ]

    if not timestamps:
        return []

    start_time = min(timestamps)
    grouped = {}

    for event in events:
        if "lat" not in event or "lon" not in event:
            continue

        timestamp = pd.Timestamp(event["timestamp"])
        elapsed_seconds = (timestamp - start_time).total_seconds()
        window_start_seconds = int(elapsed_seconds // 900) * 900

        lat = round(float(event["lat"]), 3)
        lon = round(float(event["lon"]), 3)

        key = (lat, lon, window_start_seconds)

        if key not in grouped:
            grouped[key] = {
                "zone": f"{lat}_{lon}",
                "latitude": lat,
                "longitude": lon,
                "window_start_seconds": window_start_seconds,
                "window_end_seconds": window_start_seconds + 900,
                "vehicle_count": 0,
                "incident_count": 0,
                "pothole_count": 0,
                "pedestrian_risk_count": 0,
                "congestion_count": 0,
                "confidence_total": 0.0,
                "confidence_count": 0,
            }

        summary = grouped[key]
        event_type = str(event.get("event_type", "")).lower()

        if event_type in vehicle_types:
            summary["vehicle_count"] += 1

        if event_type == "incident":
            summary["incident_count"] += 1

        if event_type == "pothole":
            summary["pothole_count"] += 1

        if event_type == "pedestrian_risk":
            summary["pedestrian_risk_count"] += 1

        if event_type == "congestion":
            summary["congestion_count"] += 1

        confidence = event.get("confidence")
        if confidence is not None:
            summary["confidence_total"] += float(confidence)
            summary["confidence_count"] += 1

    results = []

    for summary in grouped.values():
        confidence_count = summary.pop("confidence_count")
        confidence_total = summary.pop("confidence_total")

        average_confidence = (
            confidence_total / confidence_count
            if confidence_count
            else 0.0
        )

        if summary["congestion_count"] > 0:
            congestion_level = "HIGH"
        elif summary["vehicle_count"] >= 100:
            congestion_level = "MEDIUM"
        else:
            congestion_level = "LOW"

        summary["average_confidence"] = round(average_confidence, 3)
        summary["congestion_level"] = congestion_level
        results.append(summary)

    results.sort(
        key=lambda item: (
            item["window_start_seconds"],
            -item["vehicle_count"],
        )
    )

    return results


@app.get("/predictions")
def get_predictions():
    """Return RF congestion severity and GBR delay for the busiest observed zone."""
    if not ML_FEATURES_FILE.exists():
        raise HTTPException(status_code=503, detail="ML feature data not available")

    if not RF_MODEL_FILE.exists() or not GBR_MODEL_FILE.exists():
        raise HTTPException(status_code=503, detail="ML model files not available")

    df = pd.read_csv(ML_FEATURES_FILE)

    if df.empty:
        raise HTTPException(status_code=503, detail="ML feature data is empty")

    feature_names = [
        "density_score",
        "event_count",
        "pothole_ratio",
        "congestion_ratio",
        "pedestrian_risk_ratio",
        "zone_lat",
        "zone_lon",
        "hour",
        "minute",
    ]

    missing_features = [
        feature for feature in feature_names
        if feature not in df.columns
    ]

    if missing_features:
        raise HTTPException(
            status_code=500,
            detail=f"Missing ML features: {missing_features}",
        )

    busiest = df.loc[df["event_count"].idxmax()]
    X = busiest[feature_names].to_frame().T

    rf_model = joblib.load(RF_MODEL_FILE)
    gbr_model = joblib.load(GBR_MODEL_FILE)

    severity = str(rf_model.predict(X)[0])
    probabilities = rf_model.predict_proba(X)[0]

    severity_probabilities = {
        str(label): round(float(probability), 4)
        for label, probability in zip(rf_model.classes_, probabilities)
    }

    delay_minutes = float(gbr_model.predict(X)[0])

    return {
        "zone": str(busiest["zone"]),
        "latitude": float(busiest["zone_lat"]),
        "longitude": float(busiest["zone_lon"]),
        "event_count": int(busiest["event_count"]),
        "density_score": float(busiest["density_score"]),
        "congestion_severity": severity,
        "severity_probabilities": severity_probabilities,
        "estimated_delay_minutes": round(delay_minutes, 2),
        "delay_note": (
            "Prototype estimate based on the simulated training target; "
            "not real traffic-delay ground truth."
        ),
    }


@app.get("/evidence/{filename}")
def get_evidence(filename: str):
    """Serve incident evidence images from the controlled evidence directory."""
    evidence_dir = BASE_DIR / "data" / "processed" / "events" / "incident_frames"

    # Only allow a plain filename; never accept directory traversal paths.
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid evidence filename")

    evidence_file = evidence_dir / safe_name

    if not evidence_file.is_file():
        raise HTTPException(status_code=404, detail="Evidence image not found")

    return FileResponse(evidence_file)


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


# Round 3 API routes
from backend.routes import router as round3_router

app.include_router(round3_router)


@app.get("/health", tags=["Health"])
def health_check():
    """Public health check for the central backend."""
    from sqlalchemy import text
    from backend.db import engine

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "ok",
        }
    except Exception:
        return {
            "status": "degraded",
            "database": "error",
        }
