from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


POTHOLE_EVENT_THRESHOLD = 0.44
POTHOLE_MIN_HITS = 2

PEDESTRIAN_SPEED_THRESHOLD_KMH = 5.0
PEDESTRIAN_HEIGHT_THRESHOLD = 0.25
PEDESTRIAN_COOLDOWN_SECONDS = 20.0

# Normalized trapezoid coordinates:
# bottom-left, bottom-right, upper-right, upper-left.
PEDESTRIAN_ROI = np.array(
    [
        [0.30, 1.00],
        [0.70, 1.00],
        [0.60, 0.55],
        [0.40, 0.55],
    ],
    dtype=np.float32,
)


@dataclass
class TrackState:
    hits: int = 0
    confidences: List[float] = field(default_factory=list)
    best_confidence: float = 0.0
    best_frame: Optional[np.ndarray] = None
    best_bbox: Optional[Tuple[float, float, float, float]] = None
    emitted: bool = False


class EventEngine:
    """
    Stateful event engine for one connected camera/phone.

    Track state is isolated per EventEngine instance. A new engine should
    therefore be created for every independent camera stream.
    """

    def __init__(self) -> None:
        self.pothole_tracks: Dict[int, TrackState] = {}
        self.pedestrian_last_event: Dict[int, float] = {}
        self.event_counter = 0

    @staticmethod
    def _area_share(
        bbox: Tuple[float, float, float, float],
        frame_shape: Tuple[int, ...],
    ) -> float:
        height, width = frame_shape[:2]
        x1, y1, x2, y2 = bbox

        box_width = max(0.0, x2 - x1)
        box_height = max(0.0, y2 - y1)
        box_area = box_width * box_height
        frame_area = float(width * height)

        if frame_area <= 0:
            return 0.0

        return box_area / frame_area

    @staticmethod
    def pothole_severity(area_share: float) -> str:
        """
        Heuristic severity based only on bounding-box area share.

        This is a visual-size proxy, not a physical pothole-depth or
        road-damage severity measurement.
        """
        if area_share >= 0.10:
            return "high"
        if area_share >= 0.03:
            return "medium"
        return "low"

    @staticmethod
    def _foot_point_inside_roi(
        bbox: Tuple[float, float, float, float],
        frame_shape: Tuple[int, ...],
    ) -> bool:
        height, width = frame_shape[:2]
        if width <= 0 or height <= 0:
            return False

        x1, y1, x2, y2 = bbox
        foot_x = (x1 + x2) / 2.0
        foot_y = y2

        roi = PEDESTRIAN_ROI.copy()
        roi[:, 0] *= width
        roi[:, 1] *= height

        point = (float(foot_x), float(foot_y))
        return cv2.pointPolygonTest(roi.astype(np.float32), point, False) >= 0

    @staticmethod
    def _is_close_pedestrian(
        bbox: Tuple[float, float, float, float],
        frame_shape: Tuple[int, ...],
    ) -> bool:
        height = frame_shape[0]
        if height <= 0:
            return False

        box_height = max(0.0, bbox[3] - bbox[1])
        return (box_height / float(height)) > PEDESTRIAN_HEIGHT_THRESHOLD

    def update_potholes(
        self,
        detections: List[Dict],
        frame: np.ndarray,
        timestamp_s: float,
    ) -> List[Dict]:
        """
        Update pothole tracks and emit at most one event per track.

        A pothole event requires at least two observations and a mean
        confidence strictly above the A1-derived operating threshold.
        """
        events: List[Dict] = []

        for detection in detections:
            if detection.get("label") != "pothole":
                continue

            track_id = detection.get("track_id")
            if track_id is None:
                continue

            confidence = float(detection["confidence"])
            bbox = tuple(float(v) for v in detection["bbox"])

            state = self.pothole_tracks.setdefault(track_id, TrackState())

            state.hits += 1
            state.confidences.append(confidence)

            if confidence > state.best_confidence:
                state.best_confidence = confidence
                state.best_frame = frame.copy()
                state.best_bbox = bbox

            mean_confidence = sum(state.confidences) / len(state.confidences)

            if (
                not state.emitted
                and state.hits >= POTHOLE_MIN_HITS
                and mean_confidence > POTHOLE_EVENT_THRESHOLD
                and state.best_frame is not None
                and state.best_bbox is not None
            ):
                area_share = self._area_share(
                    state.best_bbox,
                    state.best_frame.shape,
                )

                self.event_counter += 1
                event = {
                    "event_id": self.event_counter,
                    "event_type": "pothole",
                    "track_id": track_id,
                    "timestamp_s": float(timestamp_s),
                    "confidence": round(mean_confidence, 4),
                    "hits": state.hits,
                    "area_share": round(area_share, 6),
                    "severity": self.pothole_severity(area_share),
                    "frame": state.best_frame,
                    "bbox": state.best_bbox,
                }

                state.emitted = True
                events.append(event)

        return events

    def update_pedestrians(
        self,
        detections: List[Dict],
        frame: np.ndarray,
        timestamp_s: float,
        speed_kmh: float,
    ) -> List[Dict]:
        """
        Emit pedestrian proximity-proxy events.

        Conditions:
        - person detection
        - foot point inside the lower-center trapezoid ROI
        - box height >25% of frame height
        - bus speed >5 km/h
        - 20-second cooldown per track
        """
        events: List[Dict] = []

        if speed_kmh <= PEDESTRIAN_SPEED_THRESHOLD_KMH:
            return events

        for detection in detections:
            if detection.get("label") != "person":
                continue

            track_id = detection.get("track_id")
            if track_id is None:
                continue

            bbox = tuple(float(v) for v in detection["bbox"])

            if not self._foot_point_inside_roi(bbox, frame.shape):
                continue

            if not self._is_close_pedestrian(bbox, frame.shape):
                continue

            last_event = self.pedestrian_last_event.get(track_id)
            if (
                last_event is not None
                and timestamp_s - last_event < PEDESTRIAN_COOLDOWN_SECONDS
            ):
                continue

            self.event_counter += 1
            self.pedestrian_last_event[track_id] = timestamp_s

            events.append(
                {
                    "event_id": self.event_counter,
                    "event_type": "pedestrian_risk",
                    "track_id": track_id,
                    "timestamp_s": float(timestamp_s),
                    "confidence": round(float(detection["confidence"]), 4),
                    "speed_kmh": round(float(speed_kmh), 2),
                    "frame": frame.copy(),
                    "bbox": bbox,
                    "risk_proxy": "ROI + box-height proximity heuristic",
                }
            )

        return events


def blur_person_heads(
    frame: np.ndarray,
    person_detections: List[Dict],
) -> np.ndarray:
    """
    Blur the upper 25% of every detected person bounding box.

    This is applied before evidence is written to disk.
    """
    output = frame.copy()
    height, width = output.shape[:2]

    for detection in person_detections:
        if detection.get("label") != "person":
            continue

        x1, y1, x2, y2 = (
            int(round(value)) for value in detection["bbox"]
        )

        x1 = max(0, min(x1, width))
        x2 = max(0, min(x2, width))
        y1 = max(0, min(y1, height))
        y2 = max(0, min(y2, height))

        if x2 <= x1 or y2 <= y1:
            continue

        box_height = y2 - y1
        blur_y2 = min(y2, y1 + max(1, int(round(box_height * 0.25))))

        region = output[y1:blur_y2, x1:x2]
        if region.size == 0:
            continue

        kernel = min(region.shape[0], region.shape[1])
        kernel = max(3, min(31, kernel // 2 * 2 + 1))

        output[y1:blur_y2, x1:x2] = cv2.GaussianBlur(
            region,
            (kernel, kernel),
            0,
        )

    return output


def save_event_evidence(
    frame: np.ndarray,
    person_detections: List[Dict],
    event_id: int,
    output_dir: Path,
    width: int = 480,
    quality: int = 60,
) -> Optional[Path]:
    """
    Save one privacy-filtered JPEG evidence image per event.

    The image is resized to 480px wide (unless already smaller) and JPEG
    quality is fixed at 60.
    """
    if frame is None or frame.size == 0:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    evidence = blur_person_heads(frame, person_detections)

    height, current_width = evidence.shape[:2]
    if current_width > width:
        new_height = max(1, int(round(height * width / current_width)))
        evidence = cv2.resize(
            evidence,
            (width, new_height),
            interpolation=cv2.INTER_AREA,
        )

    path = output_dir / f"event_{event_id:06d}.jpg"

    ok = cv2.imwrite(
        str(path),
        evidence,
        [cv2.IMWRITE_JPEG_QUALITY, int(quality)],
    )

    return path if ok else None
