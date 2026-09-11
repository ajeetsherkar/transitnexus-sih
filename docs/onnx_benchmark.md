# TransitNexus — PyTorch vs ONNX Runtime Benchmark

## Objective

Measure inference latency of the TransitNexus YOLO models using PyTorch and ONNX Runtime on the same video frames.

The benchmark provides an actual latency measurement for evaluating the ONNX edge-inference path.

## Benchmark Environment

| Property | Value |
|---|---|
| Hardware | Apple M2 |
| Platform | macOS 26.5.2 arm64 |
| Python | 3.11.13 |
| PyTorch | 2.14.0 |
| Ultralytics | 8.4.142 |
| ONNX | 1.22.0 |
| ONNX Runtime | 1.30.0 |
| ONNX Execution Provider | CPUExecutionProvider |

## Input

| Property | Value |
|---|---|
| Video | `data/raw/videos/mumbra_bhiwandi_01.mp4` |
| Resolution | 1280 × 720 |
| Source FPS | 30 FPS |
| Source frames | 900 |
| Benchmark frames | 50 |
| Inference image size | 640 × 640 |
| Warm-up runs | 5 |

The same 50 decoded video frames were supplied to both the PyTorch and ONNX versions of each model.

Video decoding time was not included in the model inference latency measurement.

## Models

### Vehicle Detection

- PyTorch: `yolov8n.pt`
- ONNX: `yolov8n.onnx`

### Pothole Detection

- PyTorch: `models/pothole_best.pt`
- ONNX: `models/pothole_best.onnx`

## Results

| Model | PyTorch Avg. (ms/frame) | ONNX Avg. (ms/frame) | ONNX Change |
|---|---:|---:|---:|
| Vehicle YOLOv8n | 33.60 | 38.12 | -13.43% |
| Pothole YOLOv8 | 63.25 | 108.43 | -71.43% |

## Additional Statistics

| Model | Runtime | Median (ms/frame) | Min (ms/frame) | Max (ms/frame) |
|---|---|---:|---:|---:|
| Vehicle YOLOv8n | PyTorch | 33.51 | 32.21 | 38.15 |
| Vehicle YOLOv8n | ONNX Runtime | 37.54 | 37.34 | 48.02 |
| Pothole YOLOv8 | PyTorch | 63.09 | 61.01 | 67.84 |
| Pothole YOLOv8 | ONNX Runtime | 101.65 | 99.57 | 150.27 |

## Interpretation

On the Apple M2 CPU test environment, ONNX Runtime was slower than the PyTorch implementation for both models.

- Vehicle YOLOv8n: ONNX was 13.43% slower.
- Pothole YOLOv8: ONNX was 71.43% slower.

This result is specific to the tested hardware, software versions, execution provider, model versions, input size, and benchmark methodology.

ONNX should therefore not be presented as providing a guaranteed latency improvement in the current prototype.

The ONNX export establishes a portable inference representation that can be evaluated and optimized for the eventual edge hardware and execution provider used by the deployed system.

## Reproducibility

Run from the project root:

```bash
python scripts/benchmark_onnx.py