import base64
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth import get_bus_from_api_key, require_admin_token, require_read_token
from backend.db import get_db
from backend.dedup import apply_report
from backend.models import Bus, Incident, Position, Report
from backend.schemas import EventIn, HeartbeatIn


router = APIRouter(prefix="/v1", tags=["Round 3 API"])


@router.post("/events")
def ingest_event(
    event: EventIn,
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Ingest one event from an authenticated bus."""

    bus = get_bus_from_api_key(x_api_key=x_api_key, db=db)

    if bus.bus_id != event.bus_id:
        raise HTTPException(
            status_code=403,
            detail="API key does not belong to this bus",
        )

    event_id = str(event.event_id)

    existing = db.get(Report, event_id)
    if existing is not None:
        return {
            "status": "duplicate",
            "event_id": event_id,
        }

    evidence = None
    if event.evidence_b64:
        evidence = base64.b64decode(event.evidence_b64)

    report = Report(
        event_id=event_id,
        bus_id=event.bus_id,
        type=event.type.value,
        confidence=event.confidence,
        lat=event.lat,
        lon=event.lon,
        accuracy_m=event.accuracy_m,
        ts=event.ts,
        source=event.source.value,
        evidence=evidence,
    )

    db.add(report)
    db.flush()

    # Deduplicate supported incident types.
    # traffic_density remains a raw report for later zone aggregation.
    incident = None
    if event.type.value != "traffic_density":
        incident = apply_report(db, report)

    db.commit()

    response = {
        "status": "accepted",
        "event_id": event_id,
    }

    if incident is not None:
        response["incident_id"] = incident.id
        response["incident_status"] = incident.status

    return response


@router.post("/heartbeat")
def ingest_heartbeat(
    heartbeat: HeartbeatIn,
    x_api_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    """Store a bus heartbeat and append a GPS position."""

    bus = get_bus_from_api_key(x_api_key=x_api_key, db=db)

    if bus.bus_id != heartbeat.bus_id:
        raise HTTPException(
            status_code=403,
            detail="API key does not belong to this bus",
        )

    now = datetime.now(timezone.utc)

    latest = db.execute(
        select(Position)
        .where(Position.bus_id == heartbeat.bus_id)
        .order_by(Position.ts.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is not None:
        latest_ts = latest.ts
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        else:
            latest_ts = latest_ts.astimezone(timezone.utc)

        heartbeat_ts = heartbeat.ts
        if heartbeat_ts.tzinfo is None:
            heartbeat_ts = heartbeat_ts.replace(tzinfo=timezone.utc)
        else:
            heartbeat_ts = heartbeat_ts.astimezone(timezone.utc)

        elapsed = (heartbeat_ts - latest_ts).total_seconds()

        if elapsed < 2:
            return {
                "status": "rate_limited",
                "bus_id": heartbeat.bus_id,
                "next_allowed_in_s": round(2 - elapsed, 3),
            }

    position = Position(
        bus_id=heartbeat.bus_id,
        lat=heartbeat.lat,
        lon=heartbeat.lon,
        speed_kmh=heartbeat.speed_kmh,
        heading=heartbeat.heading,
        accuracy_m=heartbeat.accuracy_m,
        ts=heartbeat.ts,
        received_at=now,
    )

    db.add(position)
    db.commit()

    return {
        "status": "accepted",
        "bus_id": heartbeat.bus_id,
        "ts": heartbeat.ts,
    }


@router.get("/buses")
def get_buses(
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return fleet state using the latest heartbeat for each bus."""
    buses = db.execute(
        select(Bus).order_by(Bus.bus_id)
    ).scalars().all()

    now = datetime.now(timezone.utc)
    results = []

    for bus in buses:
        latest = db.execute(
            select(Position)
            .where(Position.bus_id == bus.bus_id)
            .order_by(Position.ts.desc())
            .limit(1)
        ).scalar_one_or_none()

        latest_report = db.execute(
            select(Report)
            .where(Report.bus_id == bus.bus_id)
            .order_by(Report.ts.desc())
            .limit(1)
        ).scalar_one_or_none()

        source = (
            latest_report.source
            if latest_report is not None
            else "unknown"
        )

        if latest is None:
            results.append(
                {
                    "bus_id": bus.bus_id,
                    "camera_id": bus.camera_id,
                    "route_id": bus.route_id,
                    "latest_position": None,
                    "online": False,
                    "age_s": None,
                    "source": source,
                }
            )
            continue

        latest_ts = latest.ts
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        else:
            latest_ts = latest_ts.astimezone(timezone.utc)

        age_s = max(
            0.0,
            (now - latest_ts).total_seconds(),
        )

        results.append(
            {
                "bus_id": bus.bus_id,
                "camera_id": bus.camera_id,
                "route_id": bus.route_id,
                "latest_position": {
                    "lat": latest.lat,
                    "lon": latest.lon,
                    "accuracy_m": latest.accuracy_m,
                    "speed_kmh": latest.speed_kmh,
                    "heading": latest.heading,
                    "ts": latest.ts,
                },
                "online": age_s <= 15,
                "age_s": round(age_s, 3),
                "source": source,
            }
        )

    return results


@router.get("/incidents")
def get_incidents(
    type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    bus_id: Optional[str] = Query(default=None),
    since: Optional[datetime] = Query(default=None),
    zone: Optional[str] = Query(default=None),
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return incidents with optional filters."""

    query = select(Incident)

    if type is not None:
        query = query.where(Incident.type == type)

    if status is not None:
        query = query.where(Incident.status == status)

    if since is not None:
        query = query.where(Incident.last_seen >= since)

    if bus_id is not None:
        query = query.join(
            Report,
            Report.incident_id == Incident.id,
        ).where(
            Report.bus_id == bus_id
        ).distinct()

    query = query.order_by(Incident.last_seen.desc())

    incidents = db.execute(query).scalars().all()

    return [
        {
            "id": incident.id,
            "type": incident.type,
            "status": incident.status,
            "lat": incident.lat,
            "lon": incident.lon,
            "first_seen": incident.first_seen,
            "last_seen": incident.last_seen,
            "report_count": incident.report_count,
            "bus_count": incident.bus_count,
            "confidence": incident.confidence,
            "severity": incident.severity,
            "zone_id": incident.zone_id,
            "resolved_at": incident.resolved_at,
            "recurrence_of": incident.recurrence_of,
        }
        for incident in incidents
    ]


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: int,
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return one incident by ID."""

    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    reports = db.execute(
        select(Report)
        .where(Report.incident_id == incident.id)
        .order_by(Report.ts.desc())
    ).scalars().all()

    return {
        "id": incident.id,
        "type": incident.type,
        "status": incident.status,
        "lat": incident.lat,
        "lon": incident.lon,
        "first_seen": incident.first_seen,
        "last_seen": incident.last_seen,
        "report_count": incident.report_count,
        "bus_count": incident.bus_count,
        "confidence": incident.confidence,
        "severity": incident.severity,
        "zone_id": incident.zone_id,
        "resolved_at": incident.resolved_at,
        "recurrence_of": incident.recurrence_of,
        "reports": [
            {
                "event_id": report.event_id,
                "bus_id": report.bus_id,
                "type": report.type,
                "confidence": report.confidence,
                "lat": report.lat,
                "lon": report.lon,
                "accuracy_m": report.accuracy_m,
                "ts": report.ts,
                "source": report.source,
                "has_evidence": report.evidence is not None,
            }
            for report in reports
        ],
    }


@router.get("/stats")
def get_stats(
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return basic fleet and incident statistics."""

    bus_count = db.execute(
        select(func.count()).select_from(Bus)
    ).scalar_one()

    report_count = db.execute(
        select(func.count()).select_from(Report)
    ).scalar_one()

    incident_count = db.execute(
        select(func.count()).select_from(Incident)
    ).scalar_one()

    open_incident_count = db.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.status != "resolved")
    ).scalar_one()

    today_start = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    reports_today = db.execute(
        select(func.count())
        .select_from(Report)
        .where(Report.ts >= today_start)
    ).scalar_one()

    return {
        "buses": bus_count,
        "reports": report_count,
        "reports_today": reports_today,
        "incidents": incident_count,
        "open_incidents": open_incident_count,
    }


@router.get("/buses/{bus_id}/trail")
def get_bus_trail(
    bus_id: str,
    since: Optional[datetime] = Query(default=None),
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return a bus location trail; defaults to the previous 30 minutes."""
    bus = db.get(Bus, bus_id)
    if bus is None:
        raise HTTPException(status_code=404, detail="Bus not found")

    now = datetime.now(timezone.utc)

    if since is None:
        since = now.replace(microsecond=0)
        from datetime import timedelta
        since = since - timedelta(minutes=30)

    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    else:
        since = since.astimezone(timezone.utc)

    positions = db.execute(
        select(Position)
        .where(
            Position.bus_id == bus_id,
            Position.ts >= since,
        )
        .order_by(Position.ts.asc())
    ).scalars().all()

    return [
        {
            "lat": position.lat,
            "lon": position.lon,
            "accuracy_m": position.accuracy_m,
            "speed_kmh": position.speed_kmh,
            "heading": position.heading,
            "ts": position.ts,
        }
        for position in positions
    ]


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: int,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    """Resolve an incident using the admin token."""
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident not found",
        )

    now = datetime.now(timezone.utc)
    incident.status = "resolved"
    incident.resolved_at = now
    incident.last_seen = max(
        incident.last_seen.replace(tzinfo=timezone.utc)
        if incident.last_seen.tzinfo is None
        else incident.last_seen,
        now,
    )

    db.commit()
    db.refresh(incident)

    return {
        "status": "resolved",
        "incident_id": incident.id,
        "resolved_at": incident.resolved_at,
    }


@router.get("/evidence/{event_id}.jpg")
def get_event_evidence(
    event_id: str,
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return JPEG evidence for an event."""
    report = db.get(Report, event_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    if report.evidence is None:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found",
        )

    return Response(
        content=report.evidence,
        media_type="image/jpeg",
    )


@router.get("/zones")
def get_zones(
    _: None = Depends(require_read_token),
    db: Session = Depends(get_db),
):
    """Return monitored zone identifiers currently represented by incidents."""
    rows = db.execute(
        select(Incident.zone_id)
        .where(Incident.zone_id.is_not(None))
        .distinct()
        .order_by(Incident.zone_id)
    ).scalars().all()

    return [
        {
            "zone_id": zone_id,
        }
        for zone_id in rows
    ]
