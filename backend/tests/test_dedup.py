from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete

from backend.models import Bus, Incident, Position, Report
from backend.dedup import apply_report


@pytest.fixture()
def clean_dedup_db(db_session):
    """Start every dedup test with an empty isolated database."""
    db_session.execute(delete(Report))
    db_session.execute(delete(Position))
    db_session.execute(delete(Incident))
    db_session.execute(delete(Bus))
    db_session.commit()
    yield db_session


def add_bus(db, bus_id):
    bus = Bus(
        bus_id=bus_id,
        camera_id=f"{bus_id}-CAM",
        route_id="R-01",
        api_key_hash=f"hash-{bus_id}",
    )
    db.add(bus)
    db.commit()
    return bus


def make_report(
    bus_id,
    report_type="pothole",
    lat=19.9021,
    lon=74.4944,
    ts=None,
    confidence=0.8,
    accuracy_m=0.0,
):
    return Report(
        event_id=str(uuid4()),
        bus_id=bus_id,
        type=report_type,
        confidence=confidence,
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
        ts=ts or datetime.now(timezone.utc),
        source="simulated",
    )


def test_three_buses_within_8m_form_one_verified_incident(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")
    add_bus(db, "BUS-002")
    add_bus(db, "BUS-003")

    base_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    reports = [
        make_report("BUS-001", ts=base_time),
        make_report("BUS-002", lat=19.90215, lon=74.49440, ts=base_time),
        make_report("BUS-003", lat=19.90210, lon=74.49446, ts=base_time),
    ]

    for report in reports:
        apply_report(db, report)

    incidents = db.query(Incident).all()

    assert len(incidents) == 1
    assert incidents[0].report_count == 3
    assert incidents[0].bus_count == 3
    assert incidents[0].status == "VERIFIED"


def test_two_potholes_60m_apart_form_two_incidents(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")
    add_bus(db, "BUS-002")

    base_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    report_a = make_report(
        "BUS-001",
        lat=19.9021,
        lon=74.4944,
        ts=base_time,
    )

    report_b = make_report(
        "BUS-002",
        lat=19.90264,
        lon=74.4944,
        ts=base_time,
    )

    apply_report(db, report_a)
    apply_report(db, report_b)

    incidents = db.query(Incident).all()

    assert len(incidents) == 2


def test_same_location_different_types_form_two_incidents(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")
    add_bus(db, "BUS-002")

    base_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    pothole = make_report(
        "BUS-001",
        report_type="pothole",
        ts=base_time,
    )

    pedestrian = make_report(
        "BUS-002",
        report_type="pedestrian_risk",
        ts=base_time,
    )

    apply_report(db, pothole)
    apply_report(db, pedestrian)

    incidents = db.query(Incident).all()

    assert len(incidents) == 2
    assert {incident.type for incident in incidents} == {
        "pothole",
        "pedestrian_risk",
    }


def test_same_bus_twice_within_10_minutes_stays_one_incident(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")

    first_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    first = make_report(
        "BUS-001",
        ts=first_time,
        confidence=0.80,
    )

    second = make_report(
        "BUS-001",
        lat=19.90212,
        lon=74.49441,
        ts=first_time + timedelta(minutes=5),
        confidence=0.85,
    )

    apply_report(db, first)
    apply_report(db, second)

    incidents = db.query(Incident).all()

    assert len(incidents) == 1
    assert incidents[0].report_count == 2
    assert incidents[0].bus_count == 1


def test_pedestrian_risk_expires_after_10_minutes(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")

    first_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    first = make_report(
        "BUS-001",
        report_type="pedestrian_risk",
        ts=first_time,
    )

    second = make_report(
        "BUS-001",
        report_type="pedestrian_risk",
        ts=first_time + timedelta(minutes=15),
    )

    apply_report(db, first)
    apply_report(db, second)

    incidents = db.query(Incident).all()

    assert len(incidents) == 2


def test_pothole_remains_same_incident_after_three_days(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")

    first_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    first = make_report(
        "BUS-001",
        ts=first_time,
    )

    second = make_report(
        "BUS-001",
        lat=19.90212,
        lon=74.49441,
        ts=first_time + timedelta(days=3),
    )

    apply_report(db, first)
    apply_report(db, second)

    incidents = db.query(Incident).all()

    assert len(incidents) == 1
    assert incidents[0].report_count == 2
    assert incidents[0].bus_count == 1


def test_resolved_incident_creates_recurrence(clean_dedup_db):
    db = clean_dedup_db

    add_bus(db, "BUS-001")

    first_time = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)

    first = make_report(
        "BUS-001",
        ts=first_time,
    )

    apply_report(db, first)

    original = db.query(Incident).one()
    original.status = "RESOLVED"
    original.resolved_at = first_time + timedelta(minutes=5)
    db.commit()

    new_detection = make_report(
        "BUS-001",
        lat=19.90212,
        lon=74.49441,
        ts=first_time + timedelta(days=1),
    )

    apply_report(db, new_detection)

    incidents = (
        db.query(Incident)
        .order_by(Incident.id.asc())
        .all()
    )

    assert len(incidents) == 2
    assert incidents[0].status == "RESOLVED"
    assert incidents[1].recurrence_of == incidents[0].id
