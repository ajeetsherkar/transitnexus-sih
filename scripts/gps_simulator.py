from typing import List, Tuple


# Kopargaon MSRTC Bus Stand -> Kopargaon Railway Station
ROUTE_POINTS: List[Tuple[float, float]] = [
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


def get_gps_at_timestamp(
    timestamp_seconds: float,
    video_duration: float,
) -> Tuple[float, float]:
    """
    Interpolate latitude and longitude along ROUTE_POINTS.

    Parameters:
        timestamp_seconds: Current video timestamp in seconds.
        video_duration: Total video duration in seconds.

    Returns:
        Tuple containing (latitude, longitude).
    """

    if video_duration <= 0:
        raise ValueError("video_duration must be greater than 0")

    if timestamp_seconds < 0:
        timestamp_seconds = 0.0

    if timestamp_seconds > video_duration:
        timestamp_seconds = video_duration

    if len(ROUTE_POINTS) < 2:
        raise ValueError("At least two route points are required")

    # Normalize timestamp to a value between 0 and 1.
    progress = timestamp_seconds / video_duration

    # Map progress to the route segments.
    segment_position = progress * (len(ROUTE_POINTS) - 1)

    segment_index = min(
        int(segment_position),
        len(ROUTE_POINTS) - 2,
    )

    segment_progress = segment_position - segment_index

    lat1, lon1 = ROUTE_POINTS[segment_index]
    lat2, lon2 = ROUTE_POINTS[segment_index + 1]

    latitude = lat1 + (lat2 - lat1) * segment_progress
    longitude = lon1 + (lon2 - lon1) * segment_progress

    return latitude, longitude


if __name__ == "__main__":
    print("=" * 60)
    print("TRANSITNEXUS GPS SIMULATOR")
    print("=" * 60)
    print(f"Route points: {len(ROUTE_POINTS)}")
    print("Route: Kopargaon MSRTC Bus Stand -> Kopargaon Railway Station")
    print()

    video_duration = 30.0

    test_timestamps = [
        0.0,
        5.0,
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
    ]

    for timestamp in test_timestamps:
        lat, lon = get_gps_at_timestamp(
            timestamp_seconds=timestamp,
            video_duration=video_duration,
        )

        print(
            f"t={timestamp:>5.1f}s -> "
            f"lat={lat:.6f}, lon={lon:.6f}"
        )

    print("=" * 60)
    print("✅ GPS simulation test completed")
    print("=" * 60)
