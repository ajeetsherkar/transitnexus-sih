"""
TransitNexus Benchmark Harness

Interface contract
------------------
1. fn(x):
   Processes one input item and returns its result.

2. inputs:
   A non-empty list of input items.

3. run(fn, inputs, warmup_iters=20, iters=200):
   - Performs warm-up iterations without recording latency.
   - Performs timed iterations using time.perf_counter().
   - Cycles through the supplied inputs.
   - Records every timed iteration's latency in milliseconds.
   - Returns a list containing one latency value per timed iteration.

Measurement scope
-----------------
The function fn(x) should include preprocessing, model inference,
and detection postprocessing when connected to the real models.

Video decoding, model loading, warm-up, and result visualisation
are excluded from the timed measurement.
"""


import time


def run(fn, inputs, warmup_iters=20, iters=200):
    """
    Execute warm-up and timed benchmark iterations.

    Args:
        fn: Function that processes one input item.
        inputs: Non-empty list of input items.
        warmup_iters: Number of untimed warm-up iterations.
        iters: Number of timed iterations.

    Returns:
        List of per-iteration latency values in milliseconds.
    """
    if not callable(fn):
        raise TypeError("fn must be callable")

    if not inputs:
        raise ValueError("inputs must not be empty")

    if warmup_iters < 0 or iters <= 0:
        raise ValueError("warmup_iters must be >= 0 and iters must be > 0")

    # Warm-up: execute without recording latency.
    for i in range(warmup_iters):
        fn(inputs[i % len(inputs)])

    # Timed execution: preserve every individual measurement.
    latencies_ms = []

    for i in range(iters):
        x = inputs[i % len(inputs)]

        start = time.perf_counter()
        fn(x)
        end = time.perf_counter()

        latency_ms = (end - start) * 1000
        latencies_ms.append(latency_ms)

    return latencies_ms


import importlib.metadata
import os
import platform
import subprocess
import sys


def env_info():
    """
    Capture hardware, operating system, Python, library and Git details.
    Missing optional libraries or unavailable details are recorded as None.
    """

    # Capture installed library versions.
    packages = [
        "numpy",
        "torch",
        "onnxruntime",
        "ultralytics",
        "opencv-python",
        "psutil",
        "pandas",
    ]

    library_versions = {}

    for package in packages:
        try:
            library_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            library_versions[package] = None

    # Capture RAM when psutil is available.
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except ImportError:
        ram_gb = None

    # Capture the current Git commit.
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_commit = None

    return {
        "cpu_model": platform.processor() or None,
        "cpu_cores": os.cpu_count(),
        "ram_gb": ram_gb,
        "operating_system": platform.platform(),
        "python_version": sys.version.split()[0],
        "library_versions": library_versions,
        "git_commit": git_commit,
    }


import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np


def save(latencies_ms, output_dir, metadata=None):
    """
    Save individual latency measurements to CSV and run metadata to JSON.

    Returns:
        Dictionary containing the CSV and JSON output paths.
    """
    if not latencies_ms:
        raise ValueError("latencies_ms must not be empty")

    latencies = np.asarray(latencies_ms, dtype=float)

    if not np.all(np.isfinite(latencies)) or np.any(latencies < 0):
        raise ValueError("Latencies must be finite and non-negative")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = output_path / f"{timestamp}_latency.csv"
    json_path = output_path / f"{timestamp}_meta.json"

    # Save every individual measurement.
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "latency_ms"])

        for iteration, latency in enumerate(latencies, start=1):
            writer.writerow([iteration, float(latency)])

    # Calculate descriptive statistics.
    summary = {
        "iterations": int(len(latencies)),
        "mean_ms": float(np.mean(latencies)),
        "std_ms": float(np.std(latencies, ddof=1)) if len(latencies) > 1 else 0.0,
        "median_ms": float(np.median(latencies)),
        "p50_ms": float(np.percentile(latencies, 50)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "p99_ms": float(np.percentile(latencies, 99)),
        "min_ms": float(np.min(latencies)),
        "max_ms": float(np.max(latencies)),
    }

    document = {
        "timestamp": timestamp,
        "summary": summary,
        "environment": env_info(),
        "metadata": metadata or {},
    }

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(document, f, indent=2)

    return {
        "csv": str(csv_path),
        "json": str(json_path),
    }


def parse_args():
    """Parse benchmark configuration without loading real models."""
    import argparse

    parser = argparse.ArgumentParser(
        description="TransitNexus benchmark harness"
    )

    parser.add_argument(
        "--runtime",
        choices=["pytorch", "onnx"],
        default="pytorch"
    )
    parser.add_argument(
        "--precision",
        choices=["fp32", "fp16", "int8"],
        default="fp32"
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a dummy workload instead of a real model"
    )

    args = parser.parse_args()

    if args.imgsz <= 0 or args.batch <= 0 or args.threads <= 0:
        parser.error("imgsz, batch and threads must be positive")

    if args.iters <= 0 or args.warmup < 0:
        parser.error("iters must be positive and warmup cannot be negative")

    return args


def demo_workload(x):
    """Small deterministic workload for testing the harness."""
    return sum(value * value for value in x)


def main():
    args = parse_args()

    if not args.demo:
        print("Configuration parsed successfully.")
        print("Real model execution is not connected yet.")
        return

    inputs = [
        [1, 2, 3, 4, 5],
        [2, 3, 4, 5, 6],
        [3, 4, 5, 6, 7],
    ]

    print("Running TransitNexus dummy benchmark...")
    print(f"Runtime: {args.runtime}")
    print(f"Precision: {args.precision}")
    print(f"Image size: {args.imgsz}")
    print(f"Batch size: {args.batch}")
    print(f"Threads: {args.threads}")
    print(f"Warm-up iterations: {args.warmup}")
    print(f"Timed iterations: {args.iters}")

    latencies = run(
        demo_workload,
        inputs,
        warmup_iters=args.warmup,
        iters=args.iters
    )

    metadata = {
        "mode": "dummy_demo",
        "runtime": args.runtime,
        "precision": args.precision,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "threads": args.threads,
        "warmup_iters": args.warmup,
        "timed_iters": args.iters,
    }

    paths = save(
        latencies,
        "project-studies/transitnexus/benchmark/results",
        metadata
    )

    print("\nBenchmark completed.")
    print(f"Recorded iterations: {len(latencies)}")
    print(f"CSV: {paths['csv']}")
    print(f"JSON: {paths['json']}")


if __name__ == "__main__":
    main()
