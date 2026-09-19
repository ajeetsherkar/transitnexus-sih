from datetime import timedelta
from math import inf
from typing import Dict, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.geo import bounding_box, haversine_m
from backend.models import Incident, Report


DEDUP = {
    "pothole": {
        "radius_m": 15.0,
        "window": timedelta(days=30),
        "same_bus_gap": timedelta(minutes=10),
    },
    "pedestrian_risk": {
        "radius_m": 30.0,
        "window": timedelta(minutes=10),
        "same_bus_gap": timedelta(minutes=2),
    },
}


def _utc(value):
    """Normalize a datetime to timezone-aware UTC."""
    from datetime import timezone

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def effective_radius(report: Report) -> float:
    """Return the base radius widened by GPS uncertainty."""
    accuracy = report.accuracy_m or 0.0
    return DEDUP[report.type]["radius_m"] + min(accuracy, 25.0)


def fused_confidence(best_conf_per_bus) -> float:
    """Noisy-OR fusion of the best confidence from each bus."""
    probability_no_detection = 1.0

    for confidence in best_conf_per_bus:
        probability_no_detection *= 1.0 - max(0.0, min(1.0, confidence))

    return min(0.99, 1.0 - probability_no_detection)


def _best_confidence_per_bus(
    db: Session,
    incident: Incident,
) -> Dict[str, float]:
    """Return the highest report confidence contributed by each bus."""
    reports = db.execute(
        select(Report).where(Report.incident_id == incident.id)
    ).scalars().all()

    best = {}

    for report in reports:
        current = best.get(report.bus_id, -inf)
        if report.confidence > current:
            best[report.bus_id] = report.confidence

    return best


def find_match(
    db: Session,
    report: Report,
) -> Optional[Incident]:
    """
    Find the nearest active incident matching the report's
    type, spatial radius and time window.

    Same-bus reports are allowed to reinforce an incident only
    when they are separated by at least the configured same-bus gap.
    """
    if report.type not in DEDUP:
        return None

    cfg = DEDUP[report.type]
    radius = effective_radius(report)

    min_lat, max_lat, min_lon, max_lon = bounding_box(
        report.lat,
        report.lon,
        radius,
    )

    report_ts = _utc(report.ts)

    candidates = db.execute(
        select(Incident).where(
            Incident.type == report.type,
            Incident.status != "RESOLVED",
            Incident.last_seen >= report_ts - cfg["window"],
            Incident.lat.between(min_lat, max_lat),
            Incident.lon.between(min_lon, max_lon),
        )
    ).scalars().all()

    best = None
    best_distance = inf

    for incident in candidates:
        distance = haversine_m(
            report.lat,
            report.lon,
            incident.lat,
            incident.lon,
        )

        if distance > radius or distance >= best_distance:
            continue

        # Repeated reports from the same bus still belong to the
        # same incident. bus_count is based on distinct buses.
        best = incident
        best_distance = distance

    return best


def _weighted_centroid(
    incident: Incident,
    report: Report,
) -> tuple[float, float]:
    """Update coordinates using confidence-weighted averaging."""
    old_weight = max(incident.confidence, 0.001)
    new_weight = max(report.confidence, 0.001)

    total_weight = old_weight + new_weight

    lat = (
        incident.lat * old_weight
        + report.lat * new_weight
    ) / total_weight

    lon = (
        incident.lon * old_weight
        + report.lon * new_weight
    ) / total_weight

    return lat, lon


def _lock_dedup_transaction(db: Session) -> None:
    """Serialize dedup matching/creation on PostgreSQL.

    Supabase/PostgreSQL uses a transaction-level advisory lock so two
    simultaneous reports cannot both observe no matching incident and
    create duplicate incidents. SQLite tests do not need this lock.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('transitnexus:dedup'))")
        )


def apply_report(
    db: Session,
    report: Report,
) -> Optional[Incident]:
    """
    Apply one report to the deduplication engine.

    The caller owns the transaction. This function deliberately
    does not commit so matching and updating can happen atomically
    with the surrounding database operation.
    """
    _lock_dedup_transaction(db)

    if report.type not in DEDUP:
        db.add(report)
        db.flush()
        return None

    # Put the incoming report into the current transaction first.
    # This lets the incident aggregation see the current bus/report.
    db.add(report)
    db.flush()

    match = find_match(db, report)

    if match is None:
        # Check for a recently resolved incident that this detection
        # spatially/temporally relates to. A recurrence becomes a
        # separate active incident with recurrence_of set.
        cfg = DEDUP[report.type]
        radius = effective_radius(report)

        min_lat, max_lat, min_lon, max_lon = bounding_box(
            report.lat,
            report.lon,
            radius,
        )

        report_ts = _utc(report.ts)

        resolved_candidates = db.execute(
            select(Incident).where(
                Incident.type == report.type,
                Incident.status == "RESOLVED",
                Incident.last_seen >= report_ts - cfg["window"],
                Incident.lat.between(min_lat, max_lat),
                Incident.lon.between(min_lon, max_lon),
            )
        ).scalars().all()

        recurrence_of = None
        nearest_distance = inf

        for incident in resolved_candidates:
            distance = haversine_m(
                report.lat,
                report.lon,
                incident.lat,
                incident.lon,
            )

            if distance <= radius and distance < nearest_distance:
                recurrence_of = incident.id
                nearest_distance = distance

        incident = Incident(
            type=report.type,
            status="DETECTED",
            lat=report.lat,
            lon=report.lon,
            first_seen=report.ts,
            last_seen=report.ts,
            report_count=1,
            bus_count=1,
            confidence=report.confidence,
            severity="high",
            recurrence_of=recurrence_of,
        )

        db.add(incident)
        db.flush()

        report.incident_id = incident.id

        return incident

    # Existing active incident.
    lat, lon = _weighted_centroid(match, report)

    match.lat = lat
    match.lon = lon
    match.last_seen = max(
        _utc(match.last_seen),
        _utc(report.ts),
    )
    match.report_count += 1

    report.incident_id = match.id

    best_by_bus = _best_confidence_per_bus(db, match)

    # Include the current report before recalculating the fused confidence.
    current_best = best_by_bus.get(report.bus_id, 0.0)
    best_by_bus[report.bus_id] = max(
        current_best,
        report.confidence,
    )

    match.bus_count = len(best_by_bus)
    match.confidence = fused_confidence(best_by_bus.values())

    if match.bus_count >= 2:
        match.status = "VERIFIED"

    return match
