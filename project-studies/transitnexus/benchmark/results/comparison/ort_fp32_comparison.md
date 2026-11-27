# TransitNexus: PyTorch vs ONNX Runtime FP32 Benchmark

## Benchmark configuration

- Device: CPU
- ONNX provider: CPUExecutionProvider
- Precision: FP32
- Input size: 640 x 640
- Batch size: 1
- Warm-up iterations: 20
- Timed iterations: 200 per run
- Confidence threshold: 0.25
- NMS IoU threshold: 0.70

## Individual run results

| Runtime | Mode | Run | Mean (ms) | Median (ms) | P95 (ms) | P99 (ms) | Max (ms) |
|---|---|---|---:|---:|---:|---:|---:|
| PyTorch | Model-only | Run 1 | 47.249 | 45.314 | 57.168 | 73.945 | 84.592 |
| PyTorch | Model-only | Run 2 | 46.608 | 44.921 | 57.708 | 71.479 | 147.374 |
| PyTorch | End-to-end | Run 1 | 47.044 | 46.693 | 49.157 | 56.612 | 62.008 |
| ONNX Runtime | Model-only | Launch 1 | 36.881 | 35.187 | 49.432 | 52.068 | 63.218 |
| ONNX Runtime | Model-only | Launch 2 | 38.315 | 34.935 | 52.249 | 76.682 | 112.263 |
| ONNX Runtime | End-to-end | Launch 1 | 38.836 | 36.085 | 51.630 | 61.663 | 77.746 |
| ONNX Runtime | End-to-end | Launch 2 | 36.016 | 35.413 | 38.324 | 50.450 | 56.457 |

## Mean latency comparison

| Mode | PyTorch mean (ms) | PyTorch runs | ONNX mean (ms) | ONNX runs | ONNX mean reduction |
|---|---:|---:|---:|---:|---:|
| Model-only | 46.929 | 2 | 37.598 | 2 | 19.88% |
| End-to-end | 47.044 | 1 | 37.426 | 2 | 20.44% |

The reduction is calculated from the arithmetic mean of the available run-level means: (PyTorch mean - ONNX mean) / PyTorch mean x 100.
The two-launch average is an average of run-level means, not a pooled calculation over all 400 individual latency observations.

## Measurement scopes

- PyTorch model-only: preprocessed Torch tensor to raw model predictions.
- ONNX model-only: preprocessed NumPy tensor to ONNX raw predictions.
- PyTorch end-to-end: BGR frame through Ultralytics preprocessing, inference and NMS using model.predict.
- ONNX end-to-end: BGR frame through preprocessing, ONNX inference, NumPy-to-Torch conversion and shared Ultralytics NMS.

The end-to-end implementations are similar in purpose but not identical in execution path. Model-only also uses different input container types (Torch tensor versus NumPy array). Therefore, the measured reductions are observed benchmark differences, not perfectly controlled causal speedup estimates.

## Repeatability and limitations

- PyTorch model-only has two recorded runs.
- ONNX model-only has two recorded process launches.
- PyTorch end-to-end has one recorded run.
- ONNX end-to-end has two recorded process launches.
- The end-to-end comparison therefore has unequal run counts.
- ONNX model-only launch 2 shows a higher P99 and maximum latency than launch 1, indicating occasional latency spikes.
- The benchmark uses one fixed 200-frame video and one model.
- Results describe this machine and configuration; they should not be generalized to other hardware without further testing.

## Interpretation

ONNX Runtime FP32 recorded lower mean latency than the PyTorch baseline in both measurement modes in these experiments. The result is promising, but further controlled repetitions and identical execution scopes would strengthen the comparison.

## Source records

- `project-studies/transitnexus/benchmark/results/pytorch_baseline/model_only/model-only-run-1/20261126_120013_meta.json`
- `project-studies/transitnexus/benchmark/results/pytorch_baseline/model_only/model-only-run-2/20261126_120117_meta.json`
- `project-studies/transitnexus/benchmark/results/pytorch_baseline/end_to_end/end-to-end-run-1/20261126_120207_meta.json`
- `project-studies/transitnexus/benchmark/results/ort_fp32/model_only/launch1/20261127_223702_meta.json`
- `project-studies/transitnexus/benchmark/results/ort_fp32/model_only/launch2/20261127_223837_meta.json`
- `project-studies/transitnexus/benchmark/results/ort_fp32/end_to_end/launch1/20261127_223746_meta.json`
- `project-studies/transitnexus/benchmark/results/ort_fp32/end_to_end/launch2/20261127_223927_meta.json`
