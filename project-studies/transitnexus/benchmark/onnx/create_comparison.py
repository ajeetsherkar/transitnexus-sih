import csv
import json
from pathlib import Path

ROOT = Path("project-studies/transitnexus/benchmark/results")

RUNS = [
    ("PyTorch", "Model-only", "Run 1",
     ROOT / "pytorch_baseline/model_only/model-only-run-1/20261126_120013_meta.json"),
    ("PyTorch", "Model-only", "Run 2",
     ROOT / "pytorch_baseline/model_only/model-only-run-2/20261126_120117_meta.json"),
    ("PyTorch", "End-to-end", "Run 1",
     ROOT / "pytorch_baseline/end_to_end/end-to-end-run-1/20261126_120207_meta.json"),
    ("ONNX Runtime", "Model-only", "Launch 1",
     ROOT / "ort_fp32/model_only/launch1/20261127_223702_meta.json"),
    ("ONNX Runtime", "Model-only", "Launch 2",
     ROOT / "ort_fp32/model_only/launch2/20261127_223837_meta.json"),
    ("ONNX Runtime", "End-to-end", "Launch 1",
     ROOT / "ort_fp32/end_to_end/launch1/20261127_223746_meta.json"),
    ("ONNX Runtime", "End-to-end", "Launch 2",
     ROOT / "ort_fp32/end_to_end/launch2/20261127_223927_meta.json"),
]

records = []

for runtime, mode, run_name, path in RUNS:
    if not path.is_file():
        raise FileNotFoundError(path)

    document = json.loads(path.read_text())
    summary = document["summary"]

    records.append({
        "runtime": runtime,
        "mode": mode,
        "run": run_name,
        "iterations": summary["iterations"],
        "mean_ms": summary["mean_ms"],
        "std_ms": summary["std_ms"],
        "median_ms": summary["median_ms"],
        "p95_ms": summary["p95_ms"],
        "p99_ms": summary["p99_ms"],
        "min_ms": summary["min_ms"],
        "max_ms": summary["max_ms"],
        "source_json": str(path),
    })

output_dir = ROOT / "comparison"
output_dir.mkdir(parents=True, exist_ok=True)

csv_path = output_dir / "ort_fp32_comparison.csv"
with csv_path.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)

def average(runtime, mode, metric):
    values = [
        row[metric]
        for row in records
        if row["runtime"] == runtime and row["mode"] == mode
    ]
    return sum(values) / len(values), len(values)

comparison = []
for mode in ["Model-only", "End-to-end"]:
    pt_mean, pt_runs = average("PyTorch", mode, "mean_ms")
    onnx_mean, onnx_runs = average("ONNX Runtime", mode, "mean_ms")
    reduction = (pt_mean - onnx_mean) / pt_mean * 100

    comparison.append({
        "mode": mode,
        "pytorch_mean": pt_mean,
        "pytorch_runs": pt_runs,
        "onnx_mean": onnx_mean,
        "onnx_runs": onnx_runs,
        "reduction": reduction,
    })

md_path = output_dir / "ort_fp32_comparison.md"

lines = [
    "# TransitNexus: PyTorch vs ONNX Runtime FP32 Benchmark",
    "",
    "## Benchmark configuration",
    "",
    "- Device: CPU",
    "- ONNX provider: CPUExecutionProvider",
    "- Precision: FP32",
    "- Input size: 640 x 640",
    "- Batch size: 1",
    "- Warm-up iterations: 20",
    "- Timed iterations: 200 per run",
    "- Confidence threshold: 0.25",
    "- NMS IoU threshold: 0.70",
    "",
    "## Individual run results",
    "",
    "| Runtime | Mode | Run | Mean (ms) | Median (ms) | P95 (ms) | P99 (ms) | Max (ms) |",
    "|---|---|---|---:|---:|---:|---:|---:|",
]

for row in records:
    lines.append(
        f"| {row['runtime']} | {row['mode']} | {row['run']} "
        f"| {row['mean_ms']:.3f} | {row['median_ms']:.3f} "
        f"| {row['p95_ms']:.3f} | {row['p99_ms']:.3f} "
        f"| {row['max_ms']:.3f} |"
    )

lines.extend([
    "",
    "## Mean latency comparison",
    "",
    "| Mode | PyTorch mean (ms) | PyTorch runs | ONNX mean (ms) | ONNX runs | ONNX mean reduction |",
    "|---|---:|---:|---:|---:|---:|",
])

for item in comparison:
    lines.append(
        f"| {item['mode']} | {item['pytorch_mean']:.3f} "
        f"| {item['pytorch_runs']} | {item['onnx_mean']:.3f} "
        f"| {item['onnx_runs']} | {item['reduction']:.2f}% |"
    )

lines.extend([
    "",
    "The reduction is calculated from the arithmetic mean of the available "
    "run-level means: (PyTorch mean - ONNX mean) / PyTorch mean x 100.",
    "The two-launch average is an average of run-level means, not a pooled "
    "calculation over all 400 individual latency observations.",
    "",
    "## Measurement scopes",
    "",
    "- PyTorch model-only: preprocessed Torch tensor to raw model predictions.",
    "- ONNX model-only: preprocessed NumPy tensor to ONNX raw predictions.",
    "- PyTorch end-to-end: BGR frame through Ultralytics preprocessing, "
    "inference and NMS using model.predict.",
    "- ONNX end-to-end: BGR frame through preprocessing, ONNX inference, "
    "NumPy-to-Torch conversion and shared Ultralytics NMS.",
    "",
    "The end-to-end implementations are similar in purpose but not identical "
    "in execution path. Model-only also uses different input container types "
    "(Torch tensor versus NumPy array). Therefore, the measured reductions "
    "are observed benchmark differences, not perfectly controlled causal "
    "speedup estimates.",
    "",
    "## Repeatability and limitations",
    "",
    "- PyTorch model-only has two recorded runs.",
    "- ONNX model-only has two recorded process launches.",
    "- PyTorch end-to-end has one recorded run.",
    "- ONNX end-to-end has two recorded process launches.",
    "- The end-to-end comparison therefore has unequal run counts.",
    "- ONNX model-only launch 2 shows a higher P99 and maximum latency than "
    "launch 1, indicating occasional latency spikes.",
    "- The benchmark uses one fixed 200-frame video and one model.",
    "- Results describe this machine and configuration; they should not be "
    "generalized to other hardware without further testing.",
    "",
    "## Interpretation",
    "",
    "ONNX Runtime FP32 recorded lower mean latency than the PyTorch baseline "
    "in both measurement modes in these experiments. The result is promising, "
    "but further controlled repetitions and identical execution scopes would "
    "strengthen the comparison.",
    "",
    "## Source records",
    "",
])

for row in records:
    lines.append(f"- `{row['source_json']}`")

md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("COMPARISON CREATED")
print("CSV:", csv_path)
print("Markdown:", md_path)

print("\nMEAN LATENCY COMPARISON")
for item in comparison:
    print(
        f"{item['mode']}: PyTorch={item['pytorch_mean']:.3f} ms "
        f"({item['pytorch_runs']} runs), "
        f"ONNX={item['onnx_mean']:.3f} ms "
        f"({item['onnx_runs']} runs), "
        f"reduction={item['reduction']:.2f}%"
    )
