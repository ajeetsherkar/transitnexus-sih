from datetime import datetime, timezone, timedelta
from uuid import uuid4

from backend.tests.conftest import TEST_API_KEY, TEST_READ_TOKEN


def make_event(bus_id="TEST-BUS-001", **overrides):
    event = {
        "event_id": str(uuid4()),
        "bus_id": bus_id,
        "camera_id": "TEST-CAM-001",
        "route_id": "TEST-R-01",
        "type": "pothole",
        "confidence": 0.87,
        "severity": "high",
        "lat": 19.9021,
        "lon": 74.4944,
        "accuracy_m": 8.0,
        "speed_kmh": 24.5,
        "heading": 87.0,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "live",
    }
    event.update(overrides)
    return event


def make_heartbeat(bus_id="TEST-BUS-001"):
    return {
        "bus_id": bus_id,
        "lat": 19.9021,
        "lon": 74.4944,
        "accuracy_m": 8.0,
        "speed_kmh": 24.5,
        "heading": 87.0,
        "ts": datetime.now(timezone.utc).isoformat(),
        "status": {
            "camera": True,
            "gps": True,
            "ai_fps": 2.1,
            "queue_depth": 0,
        },
    }


def test_event_requires_api_key(client, bus):
    response = client.post(
        "/v1/events",
        json=make_event(),
    )

    assert response.status_code == 401


def test_wrong_bus_returns_403(client, bus):
    response = client.post(
        "/v1/events",
        headers={"X-API-Key": TEST_API_KEY},
        json=make_event(bus_id="OTHER-BUS-999"),
    )

    assert response.status_code == 403


def test_invalid_latitude_returns_422(client, bus):
    response = client.post(
        "/v1/events",
        headers={"X-API-Key": TEST_API_KEY},
        json=make_event(lat=91.0),
    )

    assert response.status_code == 422


def test_duplicate_event_is_idempotent(client, bus):
    event = make_event()

    first = client.post(
        "/v1/events",
        headers={"X-API-Key": TEST_API_KEY},
        json=event,
    )

    second = client.post(
        "/v1/events",
        headers={"X-API-Key": TEST_API_KEY},
        json=event,
    )

    assert first.status_code == 200
    assert first.json()["status"] == "accepted"

    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_heartbeat_online(client, bus):
    response = client.post(
        "/v1/heartbeat",
        headers={"X-API-Key": TEST_API_KEY},
        json=make_heartbeat(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    fleet = client.get(
        "/v1/buses",
        headers={"X-Read-Token": TEST_READ_TOKEN},
    )

    assert fleet.status_code == 200

    buses = fleet.json()
    test_bus = next(item for item in buses if item["bus_id"] == "TEST-BUS-001")

    assert test_bus["online"] is True
    assert test_bus["latest_position"] is not None


def test_read_endpoint_requires_read_token(client, bus):
    response = client.get("/v1/buses")

    assert response.status_code == 401


def test_read_endpoint_accepts_valid_read_token(client, bus):
    response = client.get(
        "/v1/buses",
        headers={"X-Read-Token": TEST_READ_TOKEN},
    )

    assert response.status_code == 200


def test_future_event_is_rejected(client, bus):
    future = datetime.now(timezone.utc) + timedelta(minutes=6)

    response = client.post(
        "/v1/events",
        headers={"X-API-Key": TEST_API_KEY},
        json=make_event(ts=future.isoformat()),
    )

    assert response.status_code == 422
