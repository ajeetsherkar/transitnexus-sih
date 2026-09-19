import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Allow this script to import the project packages when executed
# directly from the tools/ directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from backend.db import Base
from backend.dedup import apply_report
from backend.models import Bus, Incident, Report


EVENTS_FILE = Path("data/processed/events.json")
REPLAY_SOURCE = "round2_dedup_measurement"


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def main() -> None:
    if not EVENTS_FILE.exists():
        raise FileNotFoundError(f"Missing events file: {EVENTS_FILE}")

    with EVENTS_FILE.open("r", encoding="utf-8") as f:
        events = json.load(f)

    if not isinstance(events, list):
        raise ValueError("events.json must contain a JSON list")

    with tempfile.TemporaryDirectory(prefix="transitnexus_dedup_") as tmp:
        db_path = Path(tmp) / "dedup_measurement.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)

        with Session(engine) as db:
            buses = {}

            for event in events:
                bus_id = event["bus_id"]

                if bus_id not in buses:
                    bus = Bus(
                        bus_id=bus_id,
                        camera_id=event["camera_id"],
                        route_id=event["route_id"],
                        api_key_hash=f"measurement:{bus_id}",
                    )
                    db.add(bus)
                    buses[bus_id] = bus

            db.flush()

            for index, event in enumerate(events, start=1):
                report = Report(
                    event_id=f"round2-dedup-{index}",
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

                apply_report(db, report)

            db.commit()

            raw_reports = db.scalar(
                select(func.count()).select_from(Report)
            )

            incident_count = db.scalar(
                select(func.count()).select_from(Incident)
            )

            supported_reports = db.scalar(
                select(func.count())
                .select_from(Report)
                .where(
                    Report.type.in_(
                        ["pothole", "pedestrian_risk"]
                    )
                )
            )

            incident_report_links = db.scalar(
                select(func.count())
                .select_from(Report)
                .where(Report.incident_id.is_not(None))
            )

        print(f"ROUND2 RAW REPORTS: {raw_reports}")
        print(f"SUPPORTED DEDUP REPORTS: {supported_reports}")
        print(f"DEDUP INCIDENTS: {incident_count}")
        print(f"REPORTS LINKED TO INCIDENTS: {incident_report_links}")

        if raw_reports:
            reduction = (
                (raw_reports - incident_count) / raw_reports
            ) * 100
        else:
            reduction = 0.0

        print(f"RAW-TO-INCIDENT REDUCTION: {reduction:.2f}%")
        print("DATASET LABEL: Replayed Round-2 data")
        print("MEASUREMENT: OK")


if __name__ == "__main__":
    main()
