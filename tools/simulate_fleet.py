import argparse
import json
import math
import random
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import requests


EARTH_RADIUS_M = 6_371_000.0
HEARTBEAT_INTERVAL_S = 2.0
GPS_NOISE_M = 5.0
POTHOLE_NOISE_M = 6.0


def haversine_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

    return EARTH_RADIUS_M * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )


def offset_gps(
    lat: float,
    lon: float,
    noise_m: float,
) -> Tuple[float, float]:
    distance = random.uniform(0.0, noise_m)
    bearing = random.uniform(0.0, 2.0 * math.pi)

    dlat = (
        distance * math.cos(bearing)
        / EARTH_RADIUS_M
    )

    dlon = (
        distance * math.sin(bearing)
        / (
            EARTH_RADIUS_M
            * math.cos(math.radians(lat))
        )
    )

    return (
        lat + math.degrees(dlat),
        lon + math.degrees(dlon),
    )


def load_route(path: Path) -> List[Tuple[float, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if data.get("type") != "FeatureCollection":
        raise ValueError(f"{path}: expected FeatureCollection")

    features = data.get("features", [])
    if len(features) != 1:
        raise ValueError(f"{path}: expected exactly one feature")

    geometry = features[0].get("geometry", {})
    if geometry.get("type") != "LineString":
        raise ValueError(f"{path}: expected LineString")

    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        raise ValueError(f"{path}: route needs at least 2 points")

    return [
        (float(lat_lon[1]), float(lat_lon[0]))
        for lat_lon in coordinates
    ]


def route_lengths(
    route: List[Tuple[float, float]],
) -> List[float]:
    lengths = [0.0]

    for i in range(1, len(route)):
        segment = haversine_m(
            route[i - 1][0],
            route[i - 1][1],
            route[i][0],
            route[i][1],
        )
        lengths.append(lengths[-1] + segment)

    return lengths


def interpolate_route(
    route: List[Tuple[float, float]],
    cumulative: List[float],
    distance_m: float,
) -> Tuple[float, float]:
    total = cumulative[-1]

    if total <= 0:
        return route[0]

    distance_m = distance_m % total

    for i in range(1, len(cumulative)):
        if distance_m <= cumulative[i]:
            segment_start = cumulative[i - 1]
            segment_end = cumulative[i]
            fraction = (
                distance_m - segment_start
            ) / max(segment_end - segment_start, 1e-9)

            lat1, lon1 = route[i - 1]
            lat2, lon2 = route[i]

            return (
                lat1 + (lat2 - lat1) * fraction,
                lon1 + (lon2 - lon1) * fraction,
            )

    return route[-1]


def bearing_degrees(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dl = math.radians(lon2 - lon1)

    y = math.sin(dl) * math.cos(p2)
    x = (
        math.cos(p1) * math.sin(p2)
        - math.sin(p1) * math.cos(p2) * math.cos(dl)
    )

    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def load_keys(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("keys.json must contain {bus_id: api_key}")

    return {
        str(bus_id): str(api_key)
        for bus_id, api_key in data.items()
    }


def send_heartbeat(
    session: requests.Session,
    url: str,
    api_key: str,
    bus_id: str,
    lat: float,
    lon: float,
    speed_kmh: float,
    heading: float,
) -> None:
    payload = {
        "bus_id": bus_id,
        "lat": lat,
        "lon": lon,
        "accuracy_m": GPS_NOISE_M,
        "speed_kmh": speed_kmh,
        "heading": heading,
        "ts": datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "status": {
            "camera": True,
            "gps": True,
            "ai_fps": 2.0,
            "queue_depth": 0,
        },
    }

    response = session.post(
        f"{url.rstrip('/')}/v1/heartbeat",
        headers={"X-API-Key": api_key},
        json=payload,
        timeout=10,
    )

    response.raise_for_status()


def send_pothole(
    session: requests.Session,
    url: str,
    api_key: str,
    bus_id: str,
    lat: float,
    lon: float,
) -> dict:
    lat, lon = offset_gps(
        lat,
        lon,
        POTHOLE_NOISE_M,
    )

    payload = {
        "event_id": str(uuid.uuid4()),
        "bus_id": bus_id,
        "camera_id": f"CAM-{bus_id}",
        "route_id": "SIM-FLEET",
        "type": "pothole",
        "confidence": round(
            random.uniform(0.60, 0.95),
            3,
        ),
        "severity": "high",
        "lat": lat,
        "lon": lon,
        "accuracy_m": GPS_NOISE_M,
        "speed_kmh": 25.0,
        "heading": 90.0,
        "ts": datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "source": "simulated",
    }

    response = session.post(
        f"{url.rstrip('/')}/v1/events",
        headers={"X-API-Key": api_key},
        json=payload,
        timeout=10,
    )

    response.raise_for_status()
    return response.json()


def bus_worker(
    bus_number: int,
    bus_id: str,
    api_key: str,
    route: List[Tuple[float, float]],
    url: str,
    speed_kmh: float,
    scenario: str,
    offline_bus: int | None,
    pothole: Tuple[float, float],
    duration_s: float,
) -> None:
    session = requests.Session()

    cumulative = route_lengths(route)
    total_distance = cumulative[-1]

    speed_mps = max(speed_kmh, 1.0) / 3.6
    if scenario == "same-pothole":
        # Start every bus before the shared pothole so all buses
        # deterministically encounter the same physical location.
        pothole_distance = total_distance * 0.55
        distance_m = max(
            0.0,
            pothole_distance - 120.0 - (bus_number - 1) * 8.0,
        )
    else:
        # For normal fleet movement, distribute buses along the route.
        distance_m = (
            total_distance
            * ((bus_number - 1) / max(len(route), 1))
        )

    pothole_reported = False
    started = time.monotonic()
    last_heartbeat = 0.0

    print(
        f"[{bus_id}] START route={total_distance:.0f}m "
        f"speed={speed_kmh:.1f}km/h"
    )

    while time.monotonic() - started < duration_s:
        elapsed = time.monotonic() - started

        if (
            scenario == "offline-bus"
            and bus_number == offline_bus
            and elapsed >= 8.0
        ):
            # Stay online initially, then intentionally stop all
            # transmissions so the backend can mark this bus offline.
            time.sleep(0.5)
            continue

        distance_m += speed_mps * 0.5

        lat, lon = interpolate_route(
            route,
            cumulative,
            distance_m,
        )

        noisy_lat, noisy_lon = offset_gps(
            lat,
            lon,
            GPS_NOISE_M,
        )

        if time.monotonic() - last_heartbeat >= HEARTBEAT_INTERVAL_S:
            next_lat, next_lon = interpolate_route(
                route,
                cumulative,
                distance_m + 5.0,
            )

            heading = bearing_degrees(
                lat,
                lon,
                next_lat,
                next_lon,
            )

            try:
                send_heartbeat(
                    session,
                    url,
                    api_key,
                    bus_id,
                    noisy_lat,
                    noisy_lon,
                    speed_kmh,
                    heading,
                )
                last_heartbeat = time.monotonic()

            except requests.RequestException as exc:
                print(
                    f"[{bus_id}] heartbeat error: {exc}"
                )

        if scenario == "same-pothole" and not pothole_reported:
            distance_to_pothole = haversine_m(
                lat,
                lon,
                pothole[0],
                pothole[1],
            )

            if distance_to_pothole <= 25.0:
                try:
                    result = send_pothole(
                        session,
                        url,
                        api_key,
                        bus_id,
                        pothole[0],
                        pothole[1],
                    )

                    print(
                        f"[{bus_id}] POTHOLE -> "
                        f"{result}"
                    )

                    pothole_reported = True

                except requests.RequestException as exc:
                    print(
                        f"[{bus_id}] pothole error: {exc}"
                    )

        time.sleep(0.5)

    print(f"[{bus_id}] STOP")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TransitNexus multi-bus fleet simulator"
    )

    parser.add_argument(
        "--buses",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=25.0,
    )

    parser.add_argument(
        "--url",
        required=True,
    )

    parser.add_argument(
        "--keys",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--scenario",
        choices=[
            "same-pothole",
            "offline-bus",
        ],
        required=True,
    )

    parser.add_argument(
        "--offline-bus",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=45.0,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
    )

    args = parser.parse_args()

    if args.buses < 1:
        raise SystemExit("--buses must be >= 1")

    if args.speed <= 0:
        raise SystemExit("--speed must be > 0")

    if args.scenario == "offline-bus":
        if args.offline_bus is None:
            raise SystemExit(
                "--offline-bus is required for offline-bus"
            )

        if not 1 <= args.offline_bus <= args.buses:
            raise SystemExit(
                "--offline-bus must be between 1 and --buses"
            )

    random.seed(args.seed)

    keys = load_keys(args.keys)

    required_ids = [
        f"SIM-BUS-{i:03d}"
        for i in range(1, args.buses + 1)
    ]

    missing = [
        bus_id
        for bus_id in required_ids
        if bus_id not in keys
    ]

    if missing:
        raise SystemExit(
            "Missing API keys for: "
            + ", ".join(missing)
        )

    route_files = sorted(
        Path("tools/routes").glob("*.geojson")
    )

    if not route_files:
        raise SystemExit(
            "No GeoJSON routes found in tools/routes/"
        )

    routes = [
        load_route(path)
        for path in route_files
    ]

    # Use one fixed physical point for the same-pothole scenario.
    pothole_route = routes[0]
    pothole_cumulative = route_lengths(pothole_route)
    pothole = interpolate_route(
        pothole_route,
        pothole_cumulative,
        pothole_cumulative[-1] * 0.55,
    )

    print("=" * 64)
    print("TRANSITNEXUS MULTI-BUS FLEET SIMULATOR")
    print("=" * 64)
    print(f"Buses: {args.buses}")
    print(f"Speed: {args.speed} km/h")
    print(f"Scenario: {args.scenario}")
    print(f"Duration: {args.duration} s")
    print(f"Routes loaded: {len(routes)}")
    print(
        "GPS noise: "
        f"~{GPS_NOISE_M:.0f} m"
    )

    if args.scenario == "same-pothole":
        print(
            "Shared pothole: "
            f"{pothole[0]:.6f}, {pothole[1]:.6f}"
        )

    if args.scenario == "offline-bus":
        print(
            f"Offline bus: SIM-BUS-{args.offline_bus:03d}"
        )

    print("=" * 64)

    threads = []

    for i in range(1, args.buses + 1):
        bus_id = f"SIM-BUS-{i:03d}"
        # In the same-pothole proof, every bus must travel the
        # route containing the shared pothole so all buses can
        # independently report the same physical incident.
        if args.scenario == "same-pothole":
            route = routes[0]
        else:
            route = routes[(i - 1) % len(routes)]

        thread = threading.Thread(
            target=bus_worker,
            kwargs={
                "bus_number": i,
                "bus_id": bus_id,
                "api_key": keys[bus_id],
                "route": route,
                "url": args.url,
                "speed_kmh": args.speed,
                "scenario": args.scenario,
                "offline_bus": args.offline_bus,
                "pothole": pothole,
                "duration_s": args.duration,
            },
            daemon=True,
        )

        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("=" * 64)
    print("FLEET SIMULATION COMPLETE")
    print("=" * 64)


if __name__ == "__main__":
    main()
