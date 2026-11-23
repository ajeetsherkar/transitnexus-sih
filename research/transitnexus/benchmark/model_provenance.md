# Pothole Detection – Model Provenance

## 1. Purpose

Record the identity and provenance of the PyTorch and ONNX models
selected for the controlled benchmark experiments.

The SHA-256 checksums identify the exact files used.

## 2. Selected benchmark models

### PyTorch model

- File: `models/pothole/best.pt`
- Size: approximately 5.9 MB
- Architecture: YOLOv8n
- Task: object detection
- Class: Potholes
- SHA-256:

  `4a1eba894263fea7874eb4ea9e4dd3887bcb4e8d2bed83ccaa098f5d3e35608f`

This is the current packaged pothole model. Its checksum matches
the packaged model checksum recorded in `docs/MODEL_CARD.md`.

### ONNX model

- File: `models/pothole/best_benchmark.onnx`
- Size: approximately 12 MB
- Exported from: `models/pothole/best.pt`
- Export image size: 640 × 640
- Export device: CPU
- SHA-256:

  `57e455361cf214140f0e3563f43c20ae2800870b07313cce4558979d6d1a9aba`

The ONNX model was exported from the selected packaged PyTorch model
using Ultralytics 8.4.142 and PyTorch 2.14.0.

## 3. ONNX verification

The exported ONNX model passed `onnx.checker.check_model()`.

| Property | Value |
|---|---|
| IR version | 8 |
| Producer | pytorch |
| Producer version | 2.14.0 |
| Ultralytics version | 8.4.142 |
| Input name | images |
| Input shape | [1, 3, 640, 640] |
| Output name | output0 |
| Output shape | [1, 5, 8400] |
| Task | detect |
| Number of classes | 1 |
| Class name | Potholes |
| Batch size | 1 |
| Dynamic input | False |
| Simplified | True |

The ONNX Runtime CPU provider successfully loaded this model in
the earlier verification.

## 4. Historical model files – do not confuse

The repository also contains older model files:

- `models/pothole_best.pt`
- `models/pothole_best.onnx`

These are different artifacts from the selected benchmark pair.

The existing historical ONNX benchmark documentation
(`docs/onnx_benchmark.md`) refers to the older model paths.

Do not use those historical results as if they were measurements
of the current `models/pothole/best.pt` and
`models/pothole/best_benchmark.onnx` pair.

## 5. Benchmark reproducibility rule

Before a benchmark run:

1. Confirm both selected files exist.
2. Recalculate their SHA-256 checksums.
3. Compare the checksums with this document.
4. Record any changed model as a new artifact/version.
5. Do not silently replace either model during an experiment.

The PyTorch and ONNX models are intended to represent the same
trained weights. Prediction consistency checks are useful, but
do not imply that every prediction is identical.
