"""
TransitNexus PyTorch YOLOv8 benchmark runner.

Modes:
  model-only  : preprocessed tensor -> raw YOLO predictions
  end-to-end  : BGR frame -> preprocessing -> inference -> NMS

Video decoding, model loading and warm-up are excluded from timed measurements.
"""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO

# Import the existing benchmark harness.
BENCHMARK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCHMARK_DIR))

from bench_harness import run, save


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def read_video(video_path, expected_frames=200):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    frames = []

    while True:
        success, frame = cap.read()
        if not success:
            break
        frames.append(frame)

    cap.release()

    if len(frames) != expected_frames:
        raise RuntimeError(
            f"Expected {expected_frames} frames, got {len(frames)}"
        )

    print(f"Decoded frames: {len(frames)}")
    print(f"Frame shape: {frames[0].shape}")

    return frames


def main():
    parser = argparse.ArgumentParser(
        description="TransitNexus PyTorch YOLOv8 benchmark"
    )

    parser.add_argument(
        "--mode",
        choices=["model-only", "end-to-end"],
        required=True,
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.home() / "transitnexus-sih",
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.70)
    parser.add_argument("--launch-id", default="launch1")

    args = parser.parse_args()

    if args.batch != 1:
        parser.error("This S1 baseline supports batch size 1 only")

    if args.imgsz <= 0:
        parser.error("imgsz must be positive")

    if args.iters <= 0 or args.warmup < 0:
        parser.error("Invalid iteration settings")

    if not args.launch_id.replace("-", "").replace("_", "").isalnum():
        parser.error("launch-id may contain only letters, numbers, - and _")

    project_root = args.project_root.expanduser().resolve()
    model_path = project_root / "models/pothole/best.pt"
    video_path = project_root / "data/benchmark/bench_clip_fixed.mp4"

    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    if not video_path.is_file():
        raise FileNotFoundError(video_path)

    # Preserve PyTorch default thread settings for this environment.

    print("\n========== BENCHMARK CONFIGURATION ==========")
    print("Mode:", args.mode)
    print("Runtime: PyTorch")
    print("Device: CPU")
    print("Precision: FP32")
    print("Image size:", args.imgsz)
    print("Batch size:", args.batch)
    print("Pre-initialization intra-op threads:", torch.get_num_threads())
    print("Pre-initialization inter-op threads:", torch.get_num_interop_threads())
    print("Warm-up iterations:", args.warmup)
    print("Timed iterations:", args.iters)
    print("Confidence:", args.conf)
    print("NMS IoU:", args.iou)
    print("Launch ID:", args.launch_id)

    # Decode the video outside the timed region.
    print("\n========== VIDEO DECODING ==========")
    frames = read_video(video_path, expected_frames=200)

    # Load the model outside the timed region.
    print("\n========== MODEL LOADING ==========")
    model = YOLO(str(model_path))
    net = model.model
    net.eval()

    # Initialize the Ultralytics predictor with the exact settings.
    # This first call is setup only and is NOT a benchmark measurement.
    print("\n========== PREDICTOR INITIALIZATION ==========")
    model.predict(
        source=frames[0],
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        rect=False,
        device="cpu",
        verbose=False,
    )

    predictor = model.predictor

    if predictor is None:
        raise RuntimeError("Ultralytics predictor was not initialized")

    print("\\n========== EFFECTIVE MEASUREMENT THREADS ==========")
    print("Intra-op threads:", torch.get_num_threads())
    print("Inter-op threads:", torch.get_num_interop_threads())

    # Prepare model-only inputs outside the timed region.
    # Ultralytics preprocessing includes letterboxing and normalization.
    print("\n========== PREPROCESSING MODEL-ONLY INPUTS ==========")
    preprocessed_tensors = []

    for frame in frames:
        tensor = predictor.preprocess([frame])
        preprocessed_tensors.append(tensor)

    print("Prepared tensors:", len(preprocessed_tensors))
    print("Tensor shape:", tuple(preprocessed_tensors[0].shape))
    print("Tensor dtype:", preprocessed_tensors[0].dtype)
    print("Tensor device:", preprocessed_tensors[0].device)

    # Function 1: neural-network forward pass only.
    # Input: preprocessed FP32 tensor.
    # Output: raw YOLO predictions before NMS.
    def fn_model_only(x):
        with torch.inference_mode():
            return net(x)

    # Function 2: full Ultralytics prediction call.
    # Includes preprocessing, model inference and NMS.
    # Video decoding and visualization are excluded.
    def fn_end_to_end(frame):
        return model.predict(
            source=frame,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            rect=False,
            device="cpu",
            verbose=False,
        )

    if args.mode == "model-only":
        benchmark_function = fn_model_only
        benchmark_inputs = preprocessed_tensors
        scope = "preprocessed_tensor_to_raw_model_predictions"

    else:
        benchmark_function = fn_end_to_end
        benchmark_inputs = frames
        scope = "BGR_frame_to_preprocessing_inference_and_NMS"

    print("\n========== BENCHMARK START ==========")
    print("Measurement scope:", scope)

    latencies = run(
        benchmark_function,
        benchmark_inputs,
        warmup_iters=args.warmup,
        iters=args.iters,
    )

    print("\n========== SAVING RESULTS ==========")

    metadata = {
        "mode": args.mode,
        "measurement_scope": scope,
        "runtime": "pytorch",
        "device": "cpu",
        "precision": "fp32",
        "imgsz": args.imgsz,
        "rect": False,
        "batch": args.batch,
        "intra_op_threads": torch.get_num_threads(),
        "inter_op_threads": torch.get_num_interop_threads(),
        "warmup_iters": args.warmup,
        "timed_iters": args.iters,
        "confidence": args.conf,
        "nms_iou": args.iou,
        "launch_id": args.launch_id,
        "video_frames": len(frames),
        "video_shape": list(frames[0].shape),
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "transitnexus_git_commit": git_commit(project_root),
        "eth_preparation_git_commit": git_commit(
            BENCHMARK_DIR.parents[2]
        ),
        "model_class_names": model.names,
        "note": (
            "Model-only excludes preprocessing and NMS. "
            "End-to-end uses the Ultralytics predict call and includes "
            "preprocessing, inference and NMS. "
            "Video decoding, model loading and warm-up are excluded."
        ),
    }

    output_dir = (
        BENCHMARK_DIR / "results" / "pytorch_baseline"
        / args.mode.replace("-", "_") / args.launch_id
    )

    paths = save(latencies, output_dir, metadata)

    print("\n========== BENCHMARK SUMMARY ==========")
    print("Iterations:", len(latencies))
    print(f"Mean: {sum(latencies) / len(latencies):.3f} ms")
    print(f"Minimum: {min(latencies):.3f} ms")
    print(f"Maximum: {max(latencies):.3f} ms")
    print("CSV:", paths["csv"])
    print("JSON:", paths["json"])
    print("\nBENCHMARK RUN COMPLETED")


if __name__ == "__main__":
    main()
