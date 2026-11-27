import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import torch
from ultralytics import YOLO
from ultralytics.utils.nms import non_max_suppression

BENCHMARK_DIR = Path(__file__).resolve().parents[1]
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

    print("Decoded frames:", len(frames))
    print("Frame shape:", frames[0].shape)
    return frames


def main():
    parser = argparse.ArgumentParser(
        description="TransitNexus ONNX Runtime graph optimization A/B benchmark"
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
    parser.add_argument("--launch-id", default="run1")
    parser.add_argument(
        "--graph-optimization",
        choices=["ORT_DISABLE_ALL", "ORT_ENABLE_ALL"],
        required=True,
    )
    args = parser.parse_args()

    if args.batch != 1:
        parser.error("This benchmark supports batch size 1 only")
    if args.imgsz <= 0 or args.iters <= 0 or args.warmup < 0:
        parser.error("Invalid benchmark settings")
    if not args.launch_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Invalid launch-id")

    project_root = args.project_root.expanduser().resolve()
    onnx_path = project_root / "models/pothole/best_benchmark.onnx"
    pt_path = project_root / "models/pothole/best.pt"
    video_path = project_root / "data/benchmark/bench_clip_fixed.mp4"

    for path in [onnx_path, pt_path, video_path]:
        if not path.is_file():
            raise FileNotFoundError(path)

    print("\n========== BENCHMARK CONFIGURATION ==========")
    print("Mode:", args.mode)
    print("Runtime: ONNX Runtime")
    print("Provider: CPUExecutionProvider")
    print("Precision: FP32")
    print("Image size:", args.imgsz)
    print("Batch size:", args.batch)
    print("Warm-up iterations:", args.warmup)
    print("Timed iterations:", args.iters)
    print("Confidence:", args.conf)
    print("NMS IoU:", args.iou)
    print("Launch ID:", args.launch_id)
    print("Graph optimization:", args.graph_optimization)

    print("\n========== VIDEO DECODING ==========")
    frames = read_video(video_path)

    print("\n========== PREPROCESSOR INITIALIZATION ==========")
    preprocessing_model = YOLO(str(pt_path))
    preprocessing_model.predict(
        source=frames[0],
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        rect=False,
        device="cpu",
        verbose=False,
    )
    predictor = preprocessing_model.predictor

    if predictor is None:
        raise RuntimeError("Ultralytics predictor initialization failed")

    print("\n========== ONNX SESSION INITIALIZATION ==========")
    session_options = ort.SessionOptions()
    optimized_output_dir = (
        BENCHMARK_DIR
        / "results"
        / "ort_graph_optimization"
        / args.mode.replace("-", "_")
        / args.graph_optimization
        / args.launch_id
    )
    optimized_output_dir.mkdir(parents=True, exist_ok=True)
    optimized_model_path = optimized_output_dir / "optimized_model.onnx"
    session_options.optimized_model_filepath = str(optimized_model_path)
    session_options.graph_optimization_level = getattr(
        ort.GraphOptimizationLevel, args.graph_optimization
    )
    session = ort.InferenceSession(
        str(onnx_path),
        sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )

    providers = session.get_providers()
    if providers != ["CPUExecutionProvider"]:
        raise RuntimeError(f"Unexpected ONNX providers: {providers}")

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    print("ONNX Runtime version:", ort.__version__)
    print("Active providers:", providers)
    print("Input name:", input_name)
    print("Output name:", output_name)
    print("Input shape:", session.get_inputs()[0].shape)
    print("Output shape:", session.get_outputs()[0].shape)

    print("\n========== PREPROCESSING INPUTS ==========")
    preprocessed_inputs = []
    for frame in frames:
        tensor = predictor.preprocess([frame])
        preprocessed_inputs.append(
            np.ascontiguousarray(tensor.cpu().numpy(), dtype=np.float32)
        )

    print("Prepared inputs:", len(preprocessed_inputs))
    print("Input shape:", preprocessed_inputs[0].shape)
    print("Input dtype:", preprocessed_inputs[0].dtype)

    def fn_model_only(x):
        return session.run([output_name], {input_name: x})[0]

    def fn_end_to_end(frame):
        tensor = predictor.preprocess([frame])
        input_array = np.ascontiguousarray(
            tensor.cpu().numpy(),
            dtype=np.float32,
        )
        raw_output = session.run(
            [output_name],
            {input_name: input_array},
        )[0]

        prediction = torch.from_numpy(raw_output)
        return non_max_suppression(
            prediction,
            conf_thres=args.conf,
            iou_thres=args.iou,
            classes=None,
            agnostic=False,
            multi_label=False,
            max_det=300,
            nc=1,
            end2end=False,
        )

    if args.mode == "model-only":
        benchmark_function = fn_model_only
        benchmark_inputs = preprocessed_inputs
        scope = "preprocessed_numpy_tensor_to_onnx_raw_predictions"
    else:
        benchmark_function = fn_end_to_end
        benchmark_inputs = frames
        scope = "BGR_frame_to_preprocessing_onnx_inference_and_NMS"

    print("\n========== BENCHMARK START ==========")
    print("Measurement scope:", scope)

    latencies = run(
        benchmark_function,
        benchmark_inputs,
        warmup_iters=args.warmup,
        iters=args.iters,
    )

    metadata = {
        "mode": args.mode,
        "measurement_scope": scope,
        "runtime": "onnxruntime",
        "onnxruntime_version": ort.__version__,
        "providers": providers,
        "device": "cpu",
        "precision": "fp32",
        "graph_optimization_level": args.graph_optimization,
        "imgsz": args.imgsz,
        "rect": False,
        "batch": args.batch,
        "warmup_iters": args.warmup,
        "timed_iters": args.iters,
        "confidence": args.conf,
        "nms_iou": args.iou,
        "max_det": 300,
        "class_agnostic_nms": False,
        "multi_label": False,
        "launch_id": args.launch_id,
        "video_frames": len(frames),
        "video_shape": list(frames[0].shape),
        "onnx_model_path": str(onnx_path),
        "onnx_model_sha256": sha256_file(onnx_path),
        "pytorch_model_path": str(pt_path),
        "pytorch_model_sha256": sha256_file(pt_path),
        "transitnexus_git_commit": git_commit(project_root),
        "eth_preparation_git_commit": git_commit(
            BENCHMARK_DIR.parents[2]
        ),
        "onnx_input_name": input_name,
        "onnx_output_name": output_name,
        "onnx_input_shape": session.get_inputs()[0].shape,
        "onnx_output_shape": session.get_outputs()[0].shape,
        "note": (
            "Model-only measures ONNX inference on preprocessed FP32 "
            "NumPy inputs. End-to-end includes Ultralytics preprocessing, "
            "ONNX Runtime inference, NumPy-to-Torch conversion and shared "
            "Ultralytics NMS. Video decoding, model/session loading and "
            "warm-up are excluded. CPUExecutionProvider is explicitly used."
        ),
    }

    output_dir = (
        BENCHMARK_DIR / "results" / "ort_graph_optimization"
        / args.mode.replace("-", "_") / args.graph_optimization / args.launch_id
    )
    paths = save(latencies, output_dir, metadata)

    print("\n========== BENCHMARK SUMMARY ==========")
    print("Iterations:", len(latencies))
    print(f"Mean: {np.mean(latencies):.3f} ms")
    print(f"Median: {np.median(latencies):.3f} ms")
    print(f"P95: {np.percentile(latencies, 95):.3f} ms")
    print(f"P99: {np.percentile(latencies, 99):.3f} ms")
    print(f"Minimum: {np.min(latencies):.3f} ms")
    print(f"Maximum: {np.max(latencies):.3f} ms")
    print("CSV:", paths["csv"])
    print("JSON:", paths["json"])
    print("\nONNX BENCHMARK RUN COMPLETED")


if __name__ == "__main__":
    main()
