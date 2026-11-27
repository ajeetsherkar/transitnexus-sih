import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox

ROOT = Path.home() / "transitnexus-sih"
MODEL_PATH = ROOT / "models/pothole/best.pt"
VIDEO_PATH = ROOT / "data/benchmark/bench_clip_fixed.mp4"
IMGSZ = 640


def main():
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    ok, frame = cap.read()
    cap.release()

    if not ok:
        raise RuntimeError("Could not read benchmark video frame")

    model = YOLO(str(MODEL_PATH))

    model.predict(
        source=frame,
        imgsz=IMGSZ,
        conf=0.25,
        iou=0.70,
        rect=False,
        device="cpu",
        verbose=False,
    )

    predictor = model.predictor
    reference = predictor.preprocess([frame]).cpu().numpy()

    letterbox = LetterBox(
        new_shape=(IMGSZ, IMGSZ),
        auto=False,
        scale_fill=False,
        scaleup=True,
        center=True,
        stride=32,
        padding_value=114,
        interpolation=cv2.INTER_LINEAR,
    )

    transformed = letterbox(image=frame)
    candidate = transformed[:, :, ::-1].transpose(2, 0, 1)
    candidate = np.ascontiguousarray(
        candidate[None], dtype=np.float32
    ) / 255.0

    difference = np.abs(reference - candidate)

    print("\n===== PREPROCESSING EQUIVALENCE =====")
    print("Original frame:", frame.shape)
    print("Reference shape:", reference.shape)
    print("Candidate shape:", candidate.shape)
    print("Reference dtype:", reference.dtype)
    print("Candidate dtype:", candidate.dtype)
    print("Maximum absolute difference:", float(difference.max()))
    print("Mean absolute difference:", float(difference.mean()))
    print("Exactly equal:", bool(np.array_equal(reference, candidate)))

    if not np.allclose(reference, candidate, atol=1e-7, rtol=0):
        raise RuntimeError("Preprocessing equivalence check FAILED")

    print("\nPASS: ONNX preprocessing matches Ultralytics")


if __name__ == "__main__":
    main()
