from math import cos, radians, sin, sqrt, atan2
from typing import Tuple


EARTH_RADIUS_M = 6_371_000.0


def haversine_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Return great-circle distance between two WGS84 coordinates in metres."""
    phi1 = radians(lat1)
    phi2 = radians(lat2)

    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = (
        sin(dphi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    )

    return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))


def bounding_box(
    lat: float,
    lon: float,
    radius_m: float,
) -> Tuple[float, float, float, float]:
    """Return min_lat, max_lat, min_lon, max_lon around a point."""
    dlat = radius_m / 111_320.0

    cos_lat = cos(radians(lat))
    if abs(cos_lat) < 1e-12:
        dlon = 180.0
    else:
        dlon = radius_m / (111_320.0 * cos_lat)

    return (
        lat - dlat,
        lat + dlat,
        lon - dlon,
        lon + dlon,
    )
