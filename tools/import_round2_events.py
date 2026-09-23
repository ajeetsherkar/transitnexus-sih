import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db import Base, engine
from backend.models import Bus, Report


EVENTS_FILE = Path("data/processed/events.json")
REPLAY_SOURCE = "round2_replay"


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def replay_api_key_hash(bus_id: str) -> str:
    return hashlib.sha256(
        f"{REPLAY_SOURCE}:{bus_id}".encode()
    ).hexdigest()


def make_event_id(event: dict) -> str:
    event_key = "|".join(
        [
            REPLAY_SOURCE,
            event["bus_id"],
            event["camera_id"],
            event["route_id"],
            event["event_type"],
            event["timestamp"],
            event["frame_path"],
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, event_key))


def main() -> None:
    if not EVENTS_FILE.exists():
        raise FileNotFoundError(f"Missing events file: {EVENTS_FILE}")

    with EVENTS_FILE.open("r", encoding="utf-8") as f:
        events = json.load(f)

    if not isinstance(events, list):
        raise ValueError("events.json must contain a JSON list")

    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        buses = {}

        for event in events:
            bus_id = event["bus_id"]

            if bus_id not in buses:
                bus = session.get(Bus, bus_id)

                if bus is None:
                    bus = Bus(
                        bus_id=bus_id,
                        camera_id=event["camera_id"],
                        route_id=event["route_id"],
                        api_key_hash=replay_api_key_hash(bus_id),
                    )
                    session.add(bus)

                buses[bus_id] = bus

        session.flush()

        event_ids = [make_event_id(event) for event in events]

        existing_ids = set(
            session.scalars(
                select(Report.event_id).where(
                    Report.event_id.in_(event_ids)
                )
            ).all()
        )

        reports = []

        for event, event_id in zip(events, event_ids):
            if event_id in existing_ids:
                continue

            reports.append(
                Report(
                    event_id=event_id,
                    bus_id=event["bus_id"],
                    type=event["event_type"],
                    confidence=event["confidence"],
                    lat=event["lat"],
                    lon=event["lon"],
                    accuracy_m=None,
                    ts=parse_timestamp(event["timestamp"]),
                    incident_id=None,
                    evidence=None,
                    source=REPLAY_SOURCE,
                )
            )

        if reports:
            session.add_all(reports)

        session.commit()

        replay_count = session.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.source == REPLAY_SOURCE)
        )

        total_count = session.scalar(
            select(func.count()).select_from(Report)
        )

    print(f"ROUND2 EVENTS READ: {len(events)}")
    print(f"NEW REPORTS INSERTED: {len(reports)}")
    print(f"ROUND2 REPLAY REPORTS: {replay_count}")
    print(f"TOTAL REPORTS IN DATABASE: {total_count}")
    print(f"SOURCE: {REPLAY_SOURCE}")
    print("IMPORT: OK")


if __name__ == "__main__":
    main()
