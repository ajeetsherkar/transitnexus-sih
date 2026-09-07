from pathlib import Path
import json

from fastapi import FastAPI, Query


BASE_DIR = Path(__file__).resolve().parent.parent
EVENTS_FILE = BASE_DIR / "data" / "processed" / "events.json"


app = FastAPI(
    title="TransitNexus API",
    description="API for serving urban mobility events and congestion heatmap data.",
    version="1.0.0",
)


def load_events():
    """Load the latest events from events.json."""
    if not EVENTS_FILE.exists():
        return []

    with open(EVENTS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/")
def root():
    return {
        "project": "TransitNexus",
        "status": "running",
        "endpoints": [
            "/events",
            "/heatmap-data",
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
