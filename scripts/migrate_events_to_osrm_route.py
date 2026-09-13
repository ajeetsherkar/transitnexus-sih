import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

EVENTS_FILE = BASE_DIR / "data" / "processed" / "events.json"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "events_osrm_migrated.json"
OSRM_ROUTE_FILE = Path("/tmp/transitnexus_route.json")

# Original simulated route used when the event coordinates were generated.
OLD_ROUTE = [
    (19.884225, 74.478773),
    (19.886319, 74.479936),
    (19.888414, 74.481100),
    (19.890508, 74.482263),
    (19.893249, 74.484267),
    (19.895990, 74.486270),
    (19.898731, 74.488274),
    (19.901472, 74.490278),
    (19.902013, 74.493611),
    (19.902554, 74.496944),
    (19.903094, 74.500277),
    (19.903635, 74.503610),
]


def haversine_m(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 6371000 * 2 * math.asin(math.sqrt(h))


def cumulative_distances(route):
    distances = [0.0]

    for i in range(1, len(route)):
        distances.append(
            distances[-1] + haversine_m(route[i - 1], route[i])
        )

    return distances


def interpolate_route(route, cumulative, target_distance):
    if target_distance <= 0:
        return route[0]

    if target_distance >= cumulative[-1]:
        return route[-1]

    for i in range(1, len(route)):
        if cumulative[i] >= target_distance:
            segment_start = cumulative[i - 1]
            segment_end = cumulative[i]

            ratio = (
                target_distance - segment_start
            ) / (segment_end - segment_start)

            lat = route[i - 1][0] + (
                route[i][0] - route[i - 1][0]
            ) * ratio

            lon = route[i - 1][1] + (
                route[i][1] - route[i - 1][1]
            ) * ratio

            return lat, lon

    return route[-1]


def project_progress(point, route, cumulative):
    """
    Approximate the event's progress along the old route.

    Each event is assigned to the nearest old-route point, then the
    corresponding normalized progress is transferred to the new route.
    """
    nearest_index = min(
        range(len(route)),
        key=lambda i: haversine_m(point, route[i]),
    )

    return cumulative[nearest_index] / cumulative[-1]


def main():
    if not EVENTS_FILE.is_file():
        raise SystemExit(f"ERROR: Events file not found: {EVENTS_FILE}")

    if not OSRM_ROUTE_FILE.is_file():
        raise SystemExit(
            f"ERROR: OSRM route file not found: {OSRM_ROUTE_FILE}"
        )

    with EVENTS_FILE.open() as f:
        events = json.load(f)

    with OSRM_ROUTE_FILE.open() as f:
        osrm_data = json.load(f)

    if osrm_data.get("code") != "Ok":
        raise SystemExit(
            f"ERROR: OSRM route status: {osrm_data.get('code')}"
        )

    new_route = [
        (lat, lon)
        for lon, lat in osrm_data["routes"][0]["geometry"]["coordinates"]
    ]

    old_cumulative = cumulative_distances(OLD_ROUTE)
    new_cumulative = cumulative_distances(new_route)

    migrated = []

    for event in events:
        migrated_event = dict(event)

        if (
            isinstance(event.get("lat"), (int, float))
            and isinstance(event.get("lon"), (int, float))
        ):
            old_point = (
                float(event["lat"]),
                float(event["lon"]),
            )

            progress = project_progress(
                old_point,
                OLD_ROUTE,
                old_cumulative,
            )

            target_distance = progress * new_cumulative[-1]

            new_point = interpolate_route(
                new_route,
                new_cumulative,
                target_distance,
            )

            migrated_event["lat"] = round(new_point[0], 6)
            migrated_event["lon"] = round(new_point[1], 6)

        migrated.append(migrated_event)

    print("=== OSRM ROUTE MIGRATION DRY RUN ===")
    print(f"Events: {len(events)}")
    print(f"Old route points: {len(OLD_ROUTE)}")
    print(f"New route points: {len(new_route)}")
    print(f"New route distance: {new_cumulative[-1] / 1000:.3f} km")

    incident_before = next(
        e for e in events if e.get("event_type") == "incident"
    )

    incident_after = next(
        e for e in migrated if e.get("event_type") == "incident"
    )

    print()
    print("Incident BEFORE:")
    print(
        f"  ({incident_before['lat']}, "
        f"{incident_before['lon']})"
    )

    print("Incident AFTER:")
    print(
        f"  ({incident_after['lat']}, "
        f"{incident_after['lon']})"
    )

    print()
    with OUTPUT_FILE.open("w") as f:
        json.dump(migrated, f, indent=2)

    print(f"✓ Migrated dataset written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
