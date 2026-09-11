from pathlib import Path
import time

import cv2
import numpy as np
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent

VIDEO_PATH = BASE_DIR / "data" / "raw" / "videos" / "mumbra_bhiwandi_01.mp4"

MODELS = [
    {
        "name": "Vehicle YOLOv8n",
        "pytorch": BASE_DIR / "yolov8n.pt",
        "onnx": BASE_DIR / "yolov8n.onnx",
    },
    {
        "name": "Pothole YOLOv8",
        "pytorch": BASE_DIR / "models" / "pothole_best.pt",
        "onnx": BASE_DIR / "models" / "pothole_best.onnx",
    },
]

NUM_FRAMES = 50
IMG_SIZE = 640
WARMUP_RUNS = 5


def load_frames(video_path: Path, count: int):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    frames = []

    while len(frames) < count:
        ok, frame = cap.read()

        if not ok:
            break

        frames.append(frame)

    cap.release()

    if len(frames) < count:
        raise RuntimeError(
            f"Expected {count} frames, but only read {len(frames)}"
        )

    return frames


def benchmark(model_path: Path, frames):
    model = YOLO(str(model_path))

    # Warm-up: exclude model initialization/startup effects.
    for frame in frames[:WARMUP_RUNS]:
        model.predict(
            source=frame,
            imgsz=IMG_SIZE,
            verbose=False,
        )

    timings_ms = []

    for frame in frames:
        start = time.perf_counter()

        model.predict(
            source=frame,
            imgsz=IMG_SIZE,
            verbose=False,
        )

        end = time.perf_counter()

        timings_ms.append((end - start) * 1000)

    timings_ms = np.array(timings_ms)

    return {
        "average_ms": float(np.mean(timings_ms)),
        "median_ms": float(np.median(timings_ms)),
        "min_ms": float(np.min(timings_ms)),
        "max_ms": float(np.max(timings_ms)),
    }


def main():
    print("=" * 70)
    print("TRANSITNEXUS — PYTORCH vs ONNX RUNTIME BENCHMARK")
    print("=" * 70)
    print(f"Video       : {VIDEO_PATH}")
    print(f"Frames      : {NUM_FRAMES}")
    print(f"Image size  : {IMG_SIZE}")
    print(f"Warm-up     : {WARMUP_RUNS}")
    print("=" * 70)

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")

    for item in MODELS:
        if not item["pytorch"].exists():
            raise FileNotFoundError(
                f"PyTorch model not found: {item['pytorch']}"
            )

        if not item["onnx"].exists():
            raise FileNotFoundError(
                f"ONNX model not found: {item['onnx']}"
            )

    frames = load_frames(VIDEO_PATH, NUM_FRAMES)

    print(f"\n✓ Loaded {len(frames)} benchmark frames")

    for item in MODELS:
        print("\n" + "-" * 70)
        print(item["name"])
        print("-" * 70)

        print(f"PyTorch model: {item['pytorch']}")
        pytorch_result = benchmark(item["pytorch"], frames)

        print(f"ONNX model   : {item['onnx']}")
        onnx_result = benchmark(item["onnx"], frames)

        pytorch_ms = pytorch_result["average_ms"]
        onnx_ms = onnx_result["average_ms"]

        improvement = ((pytorch_ms - onnx_ms) / pytorch_ms) * 100

        print("\nResults:")
        print(f"PyTorch average : {pytorch_ms:.2f} ms/frame")
        print(f"ONNX average    : {onnx_ms:.2f} ms/frame")
        print(f"ONNX improvement: {improvement:.2f}%")

        print("\nAdditional statistics:")
        print(
            f"PyTorch median  : "
            f"{pytorch_result['median_ms']:.2f} ms/frame"
        )
        print(
            f"ONNX median     : "
            f"{onnx_result['median_ms']:.2f} ms/frame"
        )
        print(
            f"PyTorch range   : "
            f"{pytorch_result['min_ms']:.2f} - "
            f"{pytorch_result['max_ms']:.2f} ms"
        )
        print(
            f"ONNX range      : "
            f"{onnx_result['min_ms']:.2f} - "
            f"{onnx_result['max_ms']:.2f} ms"
        )

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
