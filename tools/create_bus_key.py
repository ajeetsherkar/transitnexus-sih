import argparse
import secrets

from backend.auth import hash_api_key
from backend.db import create_tables, engine
from backend.models import Bus
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(
        description="Create or update a TransitNexus bus API key."
    )
    parser.add_argument("--bus-id", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--route-id", required=True)

    args = parser.parse_args()

    create_tables()

    api_key = secrets.token_urlsafe(24)
    api_key_hash = hash_api_key(api_key)

    with Session(engine) as db:
        bus = db.get(Bus, args.bus_id)

        if bus is None:
            bus = Bus(
                bus_id=args.bus_id,
                camera_id=args.camera_id,
                route_id=args.route_id,
                api_key_hash=api_key_hash,
            )
            db.add(bus)
        else:
            bus.camera_id = args.camera_id
            bus.route_id = args.route_id
            bus.api_key_hash = api_key_hash

        db.commit()

    print(f"BUS ID: {args.bus_id}")
    print(f"CAMERA ID: {args.camera_id}")
    print(f"ROUTE ID: {args.route_id}")
    print()
    print("API KEY — SAVE THIS NOW:")
    print(api_key)
    print()
    print("Only the SHA-256 hash is stored in the database.")


if __name__ == "__main__":
    main()
