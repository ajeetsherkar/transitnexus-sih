from datetime import datetime, timezone, timedelta
from uuid import uuid4

from backend.tests.conftest import TEST_ADMIN_TOKEN, TEST_API_KEY, TEST_READ_TOKEN


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
    assert test_bus["source"] == "live"


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


def test_stats_reports_today(client, bus, db_session):
    from datetime import datetime, timezone, timedelta

    from backend.models import Report

    now = datetime.now(timezone.utc)

    before = db_session.query(Report).filter(
        Report.ts >= now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    ).count()

    db_session.add_all(
        [
            Report(
                event_id="00000000-0000-0000-0000-000000000001",
                bus_id=bus.bus_id,
                type="pothole",
                confidence=0.9,
                lat=19.9021,
                lon=74.4944,
                accuracy_m=8.0,
                ts=now,
                source="simulated",
            ),
            Report(
                event_id="00000000-0000-0000-0000-000000000002",
                bus_id=bus.bus_id,
                type="pothole",
                confidence=0.9,
                lat=19.9021,
                lon=74.4944,
                accuracy_m=8.0,
                ts=now - timedelta(days=1),
                source="simulated",
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/v1/stats",
        headers={"X-Read-Token": TEST_READ_TOKEN},
    )

    assert response.status_code == 200
    data = response.json()

    assert "reports_today" in data
    assert data["reports_today"] == before + 1


def test_dashboard_snapshot_is_public(client, bus):
    response = client.get("/v1/dashboard")

    assert response.status_code == 200

    data = response.json()
    assert "buses" in data
    assert "incidents" in data
    assert "stats" in data
    assert isinstance(data["buses"], list)
    assert isinstance(data["incidents"], list)
    assert isinstance(data["stats"], dict)


def test_incident_detail_returns_reports_and_evidence(client, bus, db_session):
    from backend.models import Incident, Report

    now = datetime.now(timezone.utc)
    incident = Incident(
        type="pothole",
        status="VERIFIED",
        lat=19.9021,
        lon=74.4944,
        first_seen=now - timedelta(minutes=5),
        last_seen=now,
        report_count=2,
        bus_count=1,
        confidence=0.91,
        severity="high",
    )
    db_session.add(incident)
    db_session.flush()

    report = Report(
        event_id="b1-detail-evidence-001",
        bus_id=bus.bus_id,
        type="pothole",
        confidence=0.91,
        lat=19.9021,
        lon=74.4944,
        accuracy_m=5.0,
        ts=now,
        incident_id=incident.id,
        evidence=b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9",
        source="live",
    )
    db_session.add(report)
    db_session.commit()

    response = client.get(
        f"/v1/incidents/{incident.id}",
        headers={"X-Read-Token": TEST_READ_TOKEN},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == incident.id
    assert data["status"] == "VERIFIED"
    assert len(data["reports"]) == 1
    assert data["reports"][0]["bus_id"] == bus.bus_id
    assert data["reports"][0]["event_id"] == "b1-detail-evidence-001"
    assert data["reports"][0]["has_evidence"] is True


def test_incident_evidence_requires_read_token(client, bus, db_session):
    from backend.models import Report

    report = Report(
        event_id="b1-evidence-auth-001",
        bus_id=bus.bus_id,
        type="pothole",
        confidence=0.9,
        lat=19.9021,
        lon=74.4944,
        accuracy_m=5.0,
        ts=datetime.now(timezone.utc),
        evidence=b"\xff\xd8\xff\xd9",
        source="live",
    )
    db_session.add(report)
    db_session.commit()

    response = client.get("/v1/evidence/b1-evidence-auth-001.jpg")
    assert response.status_code == 401


def test_incident_evidence_returns_jpeg(client, bus, db_session):
    from backend.models import Report

    report = Report(
        event_id="b1-evidence-001",
        bus_id=bus.bus_id,
        type="pothole",
        confidence=0.9,
        lat=19.9021,
        lon=74.4944,
        accuracy_m=5.0,
        ts=datetime.now(timezone.utc),
        evidence=b"\xff\xd8\xff\xd9",
        source="live",
    )
    db_session.add(report)
    db_session.commit()

    response = client.get(
        "/v1/evidence/b1-evidence-001.jpg",
        headers={"X-Read-Token": TEST_READ_TOKEN},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content == b"\xff\xd8\xff\xd9"


def test_resolve_incident_requires_admin_token(client, bus, db_session):
    from backend.models import Incident

    now = datetime.now(timezone.utc)
    incident = Incident(
        type="pothole",
        status="VERIFIED",
        lat=19.9021,
        lon=74.4944,
        first_seen=now,
        last_seen=now,
        report_count=1,
        bus_count=1,
        confidence=0.9,
        severity="high",
    )
    db_session.add(incident)
    db_session.commit()

    response = client.post(f"/v1/incidents/{incident.id}/resolve")
    assert response.status_code == 401


def test_resolve_incident_sets_canonical_status(client, bus, db_session):
    from backend.models import Incident

    now = datetime.now(timezone.utc)
    incident = Incident(
        type="pothole",
        status="VERIFIED",
        lat=19.9021,
        lon=74.4944,
        first_seen=now - timedelta(minutes=1),
        last_seen=now,
        report_count=1,
        bus_count=1,
        confidence=0.9,
        severity="high",
    )
    db_session.add(incident)
    db_session.commit()

    response = client.post(
        f"/v1/incidents/{incident.id}/resolve",
        headers={"X-Admin-Token": TEST_ADMIN_TOKEN},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RESOLVED"
    assert data["incident_id"] == incident.id
    assert data["resolved_at"] is not None

    db_session.refresh(incident)
    assert incident.status == "RESOLVED"
    assert incident.resolved_at is not None


def test_incident_filters_are_applied_server_side(client, bus, db_session):
    from backend.models import Incident

    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            Incident(
                type="pothole",
                status="VERIFIED",
                lat=19.9021,
                lon=74.4944,
                first_seen=now - timedelta(minutes=10),
                last_seen=now - timedelta(minutes=2),
                report_count=2,
                bus_count=2,
                confidence=0.91,
                severity="high",
            ),
            Incident(
                type="pedestrian_risk",
                status="DETECTED",
                lat=19.9031,
                lon=74.4954,
                first_seen=now - timedelta(hours=2),
                last_seen=now - timedelta(hours=1, minutes=30),
                report_count=1,
                bus_count=1,
                confidence=0.72,
                severity="medium",
            ),
            Incident(
                type="pothole",
                status="RESOLVED",
                lat=19.9041,
                lon=74.4964,
                first_seen=now - timedelta(minutes=20),
                last_seen=now - timedelta(minutes=5),
                report_count=3,
                bus_count=2,
                confidence=0.88,
                severity="high",
            ),
        ]
    )
    db_session.commit()

    headers = {"X-Read-Token": TEST_READ_TOKEN}

    response = client.get(
        "/v1/incidents?type=pothole&status=VERIFIED",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert any(
        item["lat"] == 19.9021
        and item["lon"] == 74.4944
        and item["type"] == "pothole"
        and item["status"] == "VERIFIED"
        for item in data
    )
    assert not any(
        item["lat"] == 19.9031
        and item["lon"] == 74.4954
        for item in data
    )
    assert not any(
        item["lat"] == 19.9041
        and item["lon"] == 74.4964
        for item in data
    )

    response = client.get(
        "/v1/incidents?since=" + (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert any(
        item["lat"] == 19.9021
        and item["lon"] == 74.4944
        for item in data
    )
    assert any(
        item["lat"] == 19.9041
        and item["lon"] == 74.4964
        for item in data
    )
    assert not any(
        item["lat"] == 19.9031
        and item["lon"] == 74.4954
        for item in data
    )


def test_bus_trail_minutes_filter(client, bus, db_session):
    from backend.models import Position

    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            Position(
                bus_id=bus.bus_id,
                lat=19.9000,
                lon=74.4900,
                accuracy_m=8.0,
                speed_kmh=20.0,
                heading=80.0,
                ts=now - timedelta(minutes=10),
            ),
            Position(
                bus_id=bus.bus_id,
                lat=19.9010,
                lon=74.4910,
                accuracy_m=7.0,
                speed_kmh=21.0,
                heading=82.0,
                ts=now - timedelta(minutes=3),
            ),
            Position(
                bus_id=bus.bus_id,
                lat=19.9020,
                lon=74.4920,
                accuracy_m=6.0,
                speed_kmh=22.0,
                heading=84.0,
                ts=now - timedelta(minutes=1),
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/v1/buses/TEST-BUS-001/trail?minutes=5",
        headers={"X-Read-Token": TEST_READ_TOKEN},
    )

    assert response.status_code == 200
    data = response.json()

    returned_lats = [item["lat"] for item in data]

    assert 19.9000 not in returned_lats
    assert 19.9010 in returned_lats
    assert 19.9020 in returned_lats
