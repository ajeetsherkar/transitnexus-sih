from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
from collections import defaultdict

import cv2
from ultralytics import YOLO

from gps_simulator import get_gps_at_timestamp


BASE_DIR = Path(__file__).resolve().parent.parent

VEHICLE_MODEL = BASE_DIR / "yolov8n.pt"
POTHOLE_MODEL = BASE_DIR / "models" / "pothole_best.pt"

OUTPUT_DIR = BASE_DIR / "runs" / "inference"
EVENT_DIR = BASE_DIR / "data" / "processed" / "events"
EVENTS_FILE = BASE_DIR / "data" / "processed" / "events.json"

VEHICLE_CLASSES = {
    "car",
    "bus",
    "truck",
    "motorcycle",
}

CONGESTION_THRESHOLD = 5.0
DENSITY_WINDOW_SECONDS = 5.0

# Demo pedestrian-risk zone for the Pune traffic video.
PEDESTRIAN_ZONE = (620, 330, 780, 490)


def format_timestamp(seconds: float) -> str:
    return datetime.fromtimestamp(
        seconds,
        tz=timezone.utc,
    ).isoformat()


def boxes_overlap(box_a, box_b) -> bool:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    return (
        ax1 < bx2
        and ax2 > bx1
        and ay1 < by2
        and ay2 > by1
    )


def create_event(
    event_type: str,
    confidence: float,
    lat: float,
    lon: float,
    timestamp_seconds: float,
    frame_path: str,
    density_score=None,
):
    event = {
        "event_type": event_type,
        "confidence": round(confidence, 3),
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "timestamp": format_timestamp(timestamp_seconds),
        "frame_path": frame_path,
    }

    if density_score is not None:
        event["density_score"] = round(density_score, 3)

    return event


def save_crop(frame, box, event_id: int) -> Path | None:
    height, width = frame.shape[:2]

    x1, y1, x2, y2 = map(int, box)

    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))

    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return None

    event_path = EVENT_DIR / f"event_{event_id:06d}.jpg"

    cv2.imwrite(str(event_path), crop)

    return event_path


def save_congestion_frame(frame, window_index: int) -> Path:
    start = int(window_index * DENSITY_WINDOW_SECONDS)
    end = start + int(DENSITY_WINDOW_SECONDS)

    event_path = EVENT_DIR / (
        f"congestion_{start:02d}_{end:02d}.jpg"
    )

    cv2.imwrite(str(event_path), frame)

    return event_path


def run_inference(source: str, model_type: str, confidence: float):
    source_path = Path(source)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Source not found: {source_path}"
        )

    if model_type == "vehicle":
        model_path = VEHICLE_MODEL
    elif model_type == "pothole":
        model_path = POTHOLE_MODEL
    else:
        raise ValueError(
            "model must be either 'vehicle' or 'pothole'"
        )

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    EVENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    EVENTS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 60)
    print("TRANSITNEXUS SESSION 4 EVENT EXTRACTION")
    print("=" * 60)
    print(f"Model type : {model_type}")
    print(f"Model      : {model_path}")
    print(f"Source     : {source_path}")
    print(f"Confidence : {confidence}")
    print(
        f"Congestion threshold : "
        f"{CONGESTION_THRESHOLD}"
    )
    print(
        f"Pedestrian zone      : "
        f"{PEDESTRIAN_ZONE}"
    )
    print("=" * 60)

    model = YOLO(str(model_path))

    # ---------------------------------------------------------
    # IMAGE INPUT
    # ---------------------------------------------------------

    if source_path.suffix.lower() in {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
    }:
        frame = cv2.imread(str(source_path))

        if frame is None:
            raise RuntimeError(
                f"Could not read image: {source_path}"
            )

        results = model.predict(
            source=str(source_path),
            conf=confidence,
            verbose=False,
        )

        video_duration = 1.0
        timestamp_seconds = 0.0

        lat, lon = get_gps_at_timestamp(
            timestamp_seconds,
            video_duration,
        )

        events = []

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence_score = float(box.conf[0])
                class_name = result.names[class_id]

                event_id = len(events) + 1

                event_path = save_crop(
                    frame,
                    box.xyxy[0].tolist(),
                    event_id,
                )

                if event_path is None:
                    continue

                relative_path = str(
                    event_path.relative_to(BASE_DIR)
                )

                events.append(
                    create_event(
                        event_type=class_name,
                        confidence=confidence_score,
                        lat=lat,
                        lon=lon,
                        timestamp_seconds=timestamp_seconds,
                        frame_path=relative_path,
                    )
                )

        with open(
            EVENTS_FILE,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                events,
                file,
                indent=2,
            )

        print()
        print("IMAGE EVENT SUMMARY")
        print(f"Total events: {len(events)}")
        print(f"Events file: {EVENTS_FILE}")
        print(f"Event crops: {EVENT_DIR}")
        print(
            "Note: image input has no video timeline; "
            "timestamp is 0 seconds."
        )
        print(
            "✅ Event extraction completed successfully"
        )

        return events

    # ---------------------------------------------------------
    # VIDEO INPUT
    # ---------------------------------------------------------

    capture = cv2.VideoCapture(
        str(source_path)
    )

    if not capture.isOpened():
        raise RuntimeError(
            f"Could not open video: {source_path}"
        )

    fps = capture.get(cv2.CAP_PROP_FPS)

    frame_count = int(
        capture.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if fps <= 0:
        capture.release()
        raise RuntimeError(
            "Could not determine video FPS"
        )

    video_duration = frame_count / fps

    print(
        f"Video FPS      : {fps:.2f}"
    )
    print(
        f"Video frames   : {frame_count}"
    )
    print(
        f"Video duration : {video_duration:.2f}s"
    )
    print()

    events = []

    # Each window stores:
    # vehicle detection count
    # sum of vehicle confidences
    # representative frame
    density_windows = defaultdict(
        lambda: {
            "vehicle_count": 0,
            "confidence_sum": 0.0,
            "representative_frame": None,
        }
    )

    frame_number = 0

    while True:
        success, frame = capture.read()

        if not success:
            break

        timestamp_seconds = frame_number / fps

        results = model.predict(
            source=frame,
            conf=confidence,
            verbose=False,
        )

        lat, lon = get_gps_at_timestamp(
            timestamp_seconds,
            video_duration,
        )

        current_window = int(
            timestamp_seconds
            // DENSITY_WINDOW_SECONDS
        )

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence_score = float(box.conf[0])
                class_name = result.names[class_id]

                box_coordinates = box.xyxy[0].tolist()

                # -------------------------------------------------
                # Vehicle density
                # -------------------------------------------------

                if class_name.lower() in VEHICLE_CLASSES:

                    window = density_windows[
                        current_window
                    ]

                    window["vehicle_count"] += 1
                    window[
                        "confidence_sum"
                    ] += confidence_score

                    # Keep a representative frame from
                    # the window. The latest frame is used,
                    # giving a useful view of the traffic.
                    window[
                        "representative_frame"
                    ] = frame.copy()

                # -------------------------------------------------
                # Normal detection event
                # -------------------------------------------------

                event_id = len(events) + 1

                event_path = save_crop(
                    frame,
                    box_coordinates,
                    event_id,
                )

                if event_path is not None:

                    relative_path = str(
                        event_path.relative_to(
                            BASE_DIR
                        )
                    )

                    events.append(
                        create_event(
                            event_type=class_name,
                            confidence=confidence_score,
                            lat=lat,
                            lon=lon,
                            timestamp_seconds=timestamp_seconds,
                            frame_path=relative_path,
                        )
                    )

                # -------------------------------------------------
                # Pedestrian risk
                # -------------------------------------------------

                if class_name.lower() == "person":

                    if boxes_overlap(
                        box_coordinates,
                        PEDESTRIAN_ZONE,
                    ):

                        risk_event_id = len(events) + 1

                        risk_path = save_crop(
                            frame,
                            box_coordinates,
                            risk_event_id,
                        )

                        if risk_path is not None:

                            relative_risk_path = str(
                                risk_path.relative_to(
                                    BASE_DIR
                                )
                            )

                            events.append(
                                create_event(
                                    event_type="pedestrian_risk",
                                    confidence=confidence_score,
                                    lat=lat,
                                    lon=lon,
                                    timestamp_seconds=timestamp_seconds,
                                    frame_path=relative_risk_path,
                                )
                            )

        frame_number += 1

        if frame_number % 100 == 0:
            print(
                f"Processed frame "
                f"{frame_number}/{frame_count} | "
                f"Events: {len(events)}"
            )

    capture.release()

    # ---------------------------------------------------------
    # Congestion events
    # ---------------------------------------------------------

    congestion_events = []

    complete_window_count = int(
        video_duration // DENSITY_WINDOW_SECONDS
    )

    for window_index in range(
        complete_window_count
    ):

        start_seconds = (
            window_index
            * DENSITY_WINDOW_SECONDS
        )

        end_seconds = (
            start_seconds
            + DENSITY_WINDOW_SECONDS
        )

        window = density_windows[
            window_index
        ]

        vehicle_count = window[
            "vehicle_count"
        ]

        frame_count_in_window = max(
            1,
            round(
                DENSITY_WINDOW_SECONDS
                * fps
            ),
        )

        density_score = (
            vehicle_count
            / frame_count_in_window
        )

        if density_score < CONGESTION_THRESHOLD:
            continue

        representative_frame = window[
            "representative_frame"
        ]

        if representative_frame is None:
            continue

        congestion_frame = (
            save_congestion_frame(
                representative_frame,
                window_index,
            )
        )

        average_confidence = (
            window["confidence_sum"]
            / vehicle_count
            if vehicle_count > 0
            else 0.0
        )

        midpoint = (
            start_seconds + end_seconds
        ) / 2.0

        lat, lon = get_gps_at_timestamp(
            midpoint,
            video_duration,
        )

        relative_frame_path = str(
            congestion_frame.relative_to(
                BASE_DIR
            )
        )

        congestion_event = create_event(
            event_type="congestion",
            confidence=average_confidence,
            lat=lat,
            lon=lon,
            timestamp_seconds=midpoint,
            frame_path=relative_frame_path,
            density_score=density_score,
        )

        events.append(congestion_event)
        congestion_events.append(
            congestion_event
        )

    # ---------------------------------------------------------
    # Sort events chronologically
    # ---------------------------------------------------------

    events.sort(
        key=lambda event: event["timestamp"]
    )

    # ---------------------------------------------------------
    # Save all events
    # ---------------------------------------------------------

    with open(
        EVENTS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            events,
            file,
            indent=2,
        )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    event_type_counts = defaultdict(int)

    for event in events:
        event_type_counts[
            event["event_type"]
        ] += 1

    print("\n" + "=" * 60)
    print("SESSION 4 EVENT EXTRACTION SUMMARY")
    print("=" * 60)

    print(
        f"Processed frames : {frame_number}"
    )

    print(
        f"Total events     : {len(events)}"
    )

    print()
    print("Event types:")

    for event_type, count in sorted(
        event_type_counts.items()
    ):
        print(
            f"  - {event_type}: {count}"
        )

    print()
    print(
        f"Congestion events : "
        f"{len(congestion_events)}"
    )

    print(
        f"Events file       : "
        f"{EVENTS_FILE}"
    )

    print(
        f"Event crops       : "
        f"{EVENT_DIR}"
    )

    print(
        "✅ Session 4 event extraction "
        "completed successfully"
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "TransitNexus Session 4 inference, "
            "vehicle density, and pedestrian-risk pipeline"
        )
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Path to an image or video",
    )

    parser.add_argument(
        "--model",
        required=True,
        choices=["vehicle", "pothole"],
        help="Inference model to use",
    )

    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help=(
            "Confidence threshold "
            "(default: 0.25)"
        ),
    )

    args = parser.parse_args()

    run_inference(
        source=args.source,
        model_type=args.model,
        confidence=args.conf,
    )


if __name__ == "__main__":
    main()
