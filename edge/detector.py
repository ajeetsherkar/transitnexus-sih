from pathlib import Path
from typing import Dict, List, Optional


import cv2
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent
POTHOLE_MODEL_PATH = BASE_DIR / "models" / "pothole" / "best.pt"
COCO_MODEL_PATH = BASE_DIR / "yolov8n.pt"
TRACKER_CONFIG = "bytetrack.yaml"

DEFAULT_CONFIDENCE = 0.25
DEFAULT_IMAGE_SIZE = 480


class Detector:
    """
    Per-camera detector.

    Each connected phone should own one Detector instance so the
    underlying Ultralytics model objects retain independent ByteTrack
    state across frames.
    """

    COCO_CLASS_MAP = {
        "person": "person",
        "bicycle": "bicycle",
        "car": "vehicle",
        "motorcycle": "vehicle",
        "bus": "vehicle",
        "truck": "vehicle",
    }

    def __init__(
        self,
        pothole_model_path: Path = POTHOLE_MODEL_PATH,
        coco_model_path: Path = COCO_MODEL_PATH,
        confidence: float = DEFAULT_CONFIDENCE,
        image_size: int = DEFAULT_IMAGE_SIZE,
    ) -> None:
        self.pothole_model = YOLO(str(pothole_model_path))
        self.coco_model = YOLO(str(coco_model_path))

        self.confidence = confidence
        self.image_size = image_size

    @staticmethod
    def _boxes(result, source: str) -> List[Dict]:
        detections: List[Dict] = []

        if result.boxes is None:
            return detections

        names = result.names

        for index in range(len(result.boxes)):
            box = result.boxes[index]

            xyxy = box.xyxy[0].tolist()
            confidence = float(box.conf[0].item())
            class_id = int(box.cls[0].item())

            raw_class = names[class_id]
            if source == "pothole":
                label = "pothole" if raw_class == "Potholes" else raw_class
            else:
                label = Detector.COCO_CLASS_MAP.get(raw_class)

            if label is None:
                continue

            track_id: Optional[int] = None
            if box.id is not None:
                track_id = int(box.id[0].item())

            detections.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "bbox": [float(value) for value in xyxy],
                    "track_id": track_id,
                    "source": source,
                }
            )

        return detections

    def detect(self, frame) -> Dict[str, List[Dict]]:
        """
        Run both models on one frame.

        ByteTrack state is retained by each model because persist=True.
        """
        pothole_results = self.pothole_model.track(
            frame,
            persist=True,
            tracker=TRACKER_CONFIG,
            conf=self.confidence,
            imgsz=self.image_size,
            verbose=False,
        )

        coco_results = self.coco_model.track(
            frame,
            persist=True,
            tracker=TRACKER_CONFIG,
            conf=self.confidence,
            imgsz=self.image_size,
            verbose=False,
        )

        return {
            "potholes": self._boxes(pothole_results[0], "pothole"),
            "objects": self._boxes(coco_results[0], "coco"),
        }

    @staticmethod
    def reset(detector: "Detector") -> None:
        """
        Reset tracker state for a new video/stream.

        Ultralytics stores tracker state internally on the predictor/model
        objects. Recreating the model instances is the safest explicit
        reset for a per-phone stream.
        """
        detector.pothole_model = YOLO(str(POTHOLE_MODEL_PATH))
        detector.coco_model = YOLO(str(COCO_MODEL_PATH))
