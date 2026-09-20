from pathlib import Path

import cv2
import numpy as np

from edge.events import (
    EventEngine,
    POTHOLE_EVENT_THRESHOLD,
    save_event_evidence,
)


def blank_frame():
    return np.zeros((720, 1280, 3), dtype=np.uint8)


def pothole_detection(track_id=1, confidence=0.8):
    return {
        "label": "pothole",
        "confidence": confidence,
        "bbox": [500, 400, 650, 500],
        "track_id": track_id,
    }


def person_detection(track_id=1):
    return {
        "label": "person",
        "confidence": 0.9,
        "bbox": [520, 450, 700, 700],
        "track_id": track_id,
    }


def test_pothole_requires_two_hits_and_emits_once():
    engine = EventEngine()
    frame = blank_frame()
    detection = pothole_detection()

    assert engine.update_potholes([detection], frame, 1.0) == []

    events = engine.update_potholes([detection], frame, 2.0)
    assert len(events) == 1
    assert events[0]["event_type"] == "pothole"
    assert events[0]["track_id"] == 1

    assert engine.update_potholes([detection], frame, 3.0) == []
    assert engine.event_counter == 1


def test_pothole_threshold_is_strictly_above_044():
    engine = EventEngine()
    frame = blank_frame()
    detection = pothole_detection(confidence=POTHOLE_EVENT_THRESHOLD)

    engine.update_potholes([detection], frame, 1.0)
    assert engine.update_potholes([detection], frame, 2.0) == []


def test_pothole_tracks_are_independent():
    engine = EventEngine()
    frame = blank_frame()

    engine.update_potholes(
        [pothole_detection(track_id=1)],
        frame,
        1.0,
    )
    events = engine.update_potholes(
        [pothole_detection(track_id=2)],
        frame,
        2.0,
    )

    assert events == []


def test_pedestrian_risk_requires_speed_above_5():
    engine = EventEngine()
    frame = blank_frame()
    detection = person_detection()

    result = engine.update_pedestrians(
        [detection],
        frame,
        0.0,
        speed_kmh=5.0,
    )

    assert result == []


def test_pedestrian_risk_uses_20_second_cooldown():
    engine = EventEngine()
    frame = blank_frame()
    detection = person_detection()

    first = engine.update_pedestrians(
        [detection],
        frame,
        0.0,
        speed_kmh=25.0,
    )
    second = engine.update_pedestrians(
        [detection],
        frame,
        10.0,
        speed_kmh=25.0,
    )
    third = engine.update_pedestrians(
        [detection],
        frame,
        21.0,
        speed_kmh=25.0,
    )

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


def test_person_outside_roi_does_not_trigger():
    engine = EventEngine()
    frame = blank_frame()

    detection = {
        "label": "person",
        "confidence": 0.9,
        "bbox": [50, 300, 200, 650],
        "track_id": 2,
    }

    result = engine.update_pedestrians(
        [detection],
        frame,
        0.0,
        speed_kmh=25.0,
    )

    assert result == []


def test_evidence_is_resized_to_480_width(tmp_path: Path):
    frame = blank_frame()

    path = save_event_evidence(
        frame,
        [],
        event_id=1,
        output_dir=tmp_path,
    )

    assert path is not None
    image = cv2.imread(str(path))
    assert image is not None
    assert image.shape[1] == 480
    assert image.shape[0] == 270


def test_evidence_blurs_person_head(tmp_path: Path):
    rng = np.random.default_rng(42)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pattern = rng.integers(
        0,
        256,
        (200, 200, 3),
        dtype=np.uint8,
    )

    frame[200:400, 500:700] = pattern
    frame[400:600, 500:700] = pattern

    person = {
        "label": "person",
        "bbox": [500, 200, 700, 600],
    }

    path = save_event_evidence(
        frame,
        [person],
        event_id=2,
        output_dir=tmp_path,
    )

    image = cv2.imread(str(path))
    assert image is not None

    head = image[75:150, 187:262]
    lower = image[150:225, 187:262]

    assert float(head.std()) < float(lower.std())
