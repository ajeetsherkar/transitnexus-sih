import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from backend.auth import hash_api_key
from backend.db import create_tables, engine
from backend.models import Bus

KEYS_FILE = Path("keys.json")
BUS_COUNT = 10


def main():
    if KEYS_FILE.exists():
        raise SystemExit(
            "keys.json already exists. Refusing to overwrite it."
        )

    create_tables()

    keys = {}

    with Session(engine) as db:
        for i in range(1, BUS_COUNT + 1):
            bus_id = f"SIM-BUS-{i:03d}"
            camera_id = f"CAM-SIM-{i:03d}"
            route_id = f"SIM-ROUTE-{((i - 1) % 3) + 1:02d}"

            api_key = secrets.token_urlsafe(32)

            bus = db.get(Bus, bus_id)

            if bus is None:
                bus = Bus(
                    bus_id=bus_id,
                    camera_id=camera_id,
                    route_id=route_id,
                    api_key_hash=hash_api_key(api_key),
                )
                db.add(bus)
            else:
                bus.camera_id = camera_id
                bus.route_id = route_id
                bus.api_key_hash = hash_api_key(api_key)

            keys[bus_id] = api_key

        db.commit()

    KEYS_FILE.write_text(
        json.dumps(keys, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=" * 60)
    print("SIMULATOR FLEET CREATED")
    print("=" * 60)
    print(f"BUSES: {len(keys)}")
    print(f"KEY FILE: {KEYS_FILE}")
    print("DATABASE: API key hashes stored")
    print("PLAINTEXT KEYS: local keys.json only")
    print("GIT STATUS: keys.json is ignored")
    print("=" * 60)


if __name__ == "__main__":
    main()
