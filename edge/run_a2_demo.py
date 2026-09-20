from pathlib import Path

import cv2

from edge.detector import Detector
from edge.events import EventEngine, save_event_evidence


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_VIDEO = BASE_DIR / "data" / "raw" / "videos" / "mumbra_bhiwandi_01.mp4"
OUTPUT_VIDEO = BASE_DIR / "out" / "annotated.mp4"
EVIDENCE_DIR = BASE_DIR / "out" / "a2_events"


def draw_box(frame, detection, color, label):
    x1, y1, x2, y2 = (
        int(round(value)) for value in detection["bbox"]
    )

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        color,
        2,
    )

    track_id = detection.get("track_id")
    confidence = detection.get("confidence", 0.0)

    text = f"{label} {confidence:.2f}"
    if track_id is not None:
        text += f" ID:{track_id}"

    cv2.putText(
        frame,
        text,
        (x1, max(20, y1 - 7)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
        cv2.LINE_AA,
    )


def main():
    OUTPUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(INPUT_VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open {INPUT_VIDEO}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = cv2.VideoWriter(
        str(OUTPUT_VIDEO),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Unable to create {OUTPUT_VIDEO}")

    detector = Detector(image_size=480)
    event_engine = EventEngine()

    frame_index = 0
    pothole_event_count = 0
    pedestrian_event_count = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        timestamp_s = frame_index / fps
        result = detector.detect(frame)

        objects = result["objects"]
        potholes = result["potholes"]

        for detection in objects:
            if detection["label"] == "person":
                color = (0, 200, 255)
            elif detection["label"] == "bicycle":
                color = (255, 200, 0)
            else:
                color = (0, 255, 0)

            draw_box(
                frame,
                detection,
                color,
                detection["label"],
            )

        for detection in potholes:
            draw_box(
                frame,
                detection,
                (0, 0, 255),
                "POTHOLE",
            )

        pothole_events = event_engine.update_potholes(
            potholes,
            frame,
            timestamp_s,
        )

        pedestrian_events = event_engine.update_pedestrians(
            objects,
            frame,
            timestamp_s,
            speed_kmh=25.0,
        )

        person_detections = [
            obj for obj in objects
            if obj["label"] == "person"
        ]

        for event in pothole_events + pedestrian_events:
            evidence_path = save_event_evidence(
                event["frame"],
                person_detections,
                event["event_id"],
                EVIDENCE_DIR,
            )

            if event["event_type"] == "pothole":
                pothole_event_count += 1
            else:
                pedestrian_event_count += 1

            cv2.putText(
                frame,
                f"EVENT {event['event_id']}: {event['event_type']}",
                (20, height - 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

            if evidence_path:
                print(
                    f"Event {event['event_id']} evidence: "
                    f"{evidence_path}"
                )

        cv2.putText(
            frame,
            f"TransitNexus A2 | t={timestamp_s:.1f}s",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        tracked_count = sum(
            1 for obj in objects
            if obj.get("track_id") is not None
        )

        cv2.putText(
            frame,
            f"Tracked: {tracked_count}",
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            frame,
            (
                f"Pothole events: {pothole_event_count}  "
                f"Ped-risk events: {pedestrian_event_count}"
            ),
            (20, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        writer.write(frame)
        frame_index += 1

    cap.release()
    writer.release()

    print("Frames written:", frame_index)
    print("Pothole events:", pothole_event_count)
    print("Pedestrian-risk events:", pedestrian_event_count)
    print("Output:", OUTPUT_VIDEO)
    print("Output bytes:", OUTPUT_VIDEO.stat().st_size)


if __name__ == "__main__":
    main()
