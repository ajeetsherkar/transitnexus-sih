from pathlib import Path
import argparse
import json
from datetime import datetime, timezone

import cv2
from ultralytics import YOLO

from gps_simulator import get_gps_at_timestamp


BASE_DIR = Path(__file__).resolve().parent.parent

VEHICLE_MODEL = BASE_DIR / "yolov8n.pt"
POTHOLE_MODEL = BASE_DIR / "models" / "pothole_best.pt"

OUTPUT_DIR = BASE_DIR / "runs" / "inference"
EVENT_DIR = BASE_DIR / "data" / "processed" / "events"
EVENTS_FILE = BASE_DIR / "data" / "processed" / "events.json"


def format_timestamp(seconds: float) -> str:
    """Convert video seconds into an ISO-8601 timestamp."""
    return datetime.fromtimestamp(
        seconds,
        tz=timezone.utc,
    ).isoformat()


def run_inference(source: str, model_type: str, confidence: float):
    source_path = Path(source)

    if not source_path.exists():
        raise FileNotFoundError(f"Source not found: {source_path}")

    if model_type == "vehicle":
        model_path = VEHICLE_MODEL
    elif model_type == "pothole":
        model_path = POTHOLE_MODEL
    else:
        raise ValueError("model must be either 'vehicle' or 'pothole'")

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("TRANSITNEXUS EVENT EXTRACTION")
    print("=" * 60)
    print(f"Model type : {model_type}")
    print(f"Model      : {model_path}")
    print(f"Source     : {source_path}")
    print(f"Confidence : {confidence}")
    print("=" * 60)

    model = YOLO(str(model_path))

    # Image input
    if source_path.suffix.lower() in {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
    }:
        frame = cv2.imread(str(source_path))

        if frame is None:
            raise RuntimeError(f"Could not read image: {source_path}")

        height, width = frame.shape[:2]

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
            for detection_index, box in enumerate(
                result.boxes,
                start=1,
            ):
                class_id = int(box.cls[0])
                confidence_score = float(box.conf[0])
                class_name = result.names[class_id]

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist(),
                )

                x1 = max(0, min(x1, width - 1))
                y1 = max(0, min(y1, height - 1))
                x2 = max(0, min(x2, width))
                y2 = max(0, min(y2, height))

                crop = frame[y1:y2, x1:x2]

                if crop.size == 0:
                    continue

                event_filename = (
                    f"event_{detection_index:06d}.jpg"
                )

                event_path = EVENT_DIR / event_filename

                cv2.imwrite(
                    str(event_path),
                    crop,
                )

                event = {
                    "event_type": class_name,
                    "confidence": round(
                        confidence_score,
                        3,
                    ),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "timestamp": format_timestamp(
                        timestamp_seconds
                    ),
                    "frame_path": str(
                        event_path.relative_to(BASE_DIR)
                    ),
                }

                events.append(event)

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

        print(f"Processed results: {len(results)}")
        print(f"Total events: {len(events)}")
        print(f"Events file: {EVENTS_FILE}")
        print(f"Event crops: {EVENT_DIR}")
        print("✅ Event extraction completed successfully")

        return events

    # Video input
    capture = cv2.VideoCapture(str(source_path))

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
        raise RuntimeError("Could not determine video FPS")

    video_duration = frame_count / fps

    print(f"Video FPS      : {fps:.2f}")
    print(f"Video frames   : {frame_count}")
    print(f"Video duration : {video_duration:.2f}s")
    print()

    events = []
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

        height, width = frame.shape[:2]

        lat, lon = get_gps_at_timestamp(
            timestamp_seconds,
            video_duration,
        )

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence_score = float(box.conf[0])
                class_name = result.names[class_id]

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist(),
                )

                x1 = max(0, min(x1, width - 1))
                y1 = max(0, min(y1, height - 1))
                x2 = max(0, min(x2, width))
                y2 = max(0, min(y2, height))

                crop = frame[y1:y2, x1:x2]

                if crop.size == 0:
                    continue

                event_id = len(events) + 1

                event_filename = (
                    f"event_{event_id:06d}.jpg"
                )

                event_path = EVENT_DIR / event_filename

                cv2.imwrite(
                    str(event_path),
                    crop,
                )

                event = {
                    "event_type": class_name,
                    "confidence": round(
                        confidence_score,
                        3,
                    ),
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "timestamp": format_timestamp(
                        timestamp_seconds
                    ),
                    "frame_path": str(
                        event_path.relative_to(BASE_DIR)
                    ),
                }

                events.append(event)

        frame_number += 1

        if frame_number % 100 == 0:
            print(
                f"Processed frame {frame_number}/"
                f"{frame_count} | "
                f"Events: {len(events)}"
            )

    capture.release()

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

    print("\n" + "=" * 60)
    print("EVENT EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Processed frames : {frame_number}")
    print(f"Total events     : {len(events)}")
    print(f"Events file      : {EVENTS_FILE}")
    print(f"Event crops      : {EVENT_DIR}")
    print("✅ Event extraction completed successfully")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "TransitNexus inference and structured "
            "event extraction pipeline"
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
