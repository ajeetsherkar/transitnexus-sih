
# S3 — Fundamentals: ONNX and ONNX Runtime

## Task 1: ONNX Runtime and Execution Providers

### 1. What is ONNX?
ONNX (Open Neural Network Exchange) is an open format used to represent machine-learning models so they can work across different frameworks and platforms.

### 2. What is ONNX Runtime?
ONNX Runtime (ORT) is an inference engine that loads ONNX models and executes their operations.

### 3. What is an Execution Provider (EP)?
An Execution Provider is a backend that assigns ONNX model operations to supported hardware.

Think of it as choosing the hardware engine for inference.

| Execution Provider | Where it runs |
|---|---|
| CPUExecutionProvider | CPU |
| CUDAExecutionProvider | NVIDIA GPU using CUDA |
| CoreMLExecutionProvider | Apple Core ML-supported hardware |
| TensorrtExecutionProvider | NVIDIA GPU using TensorRT |

### 4. Execution Providers for My Setup

- CPUExecutionProvider: Runs inference on CPU; my TransitNexus benchmark baseline.
- CoreMLExecutionProvider: Uses Apple's Core ML framework and compatible Apple hardware.
- CUDAExecutionProvider: Uses NVIDIA GPUs; not applicable to my MacBook Air.
- TensorrtExecutionProvider: Uses NVIDIA TensorRT; not applicable to my current setup.

Provider availability depends on the installed ONNX Runtime build.

### 5. Provider Priority
ONNX Runtime can use multiple providers in priority order.

Example:
[CUDAExecutionProvider, CPUExecutionProvider]

It tries CUDA first and uses CPU for operations that CUDA cannot execute.

### Key Takeaway
For my TransitNexus PyTorch vs ONNX Runtime benchmark, CPUExecutionProvider is the baseline. I will document the available providers before configuring the inference session.


## Task 2: ONNX Runtime Session Options

### 1. intra_op_num_threads
Controls the number of CPU threads used to perform a single operation.

### 2. graph_optimization_level
Controls the level of graph optimization applied by ONNX Runtime to improve execution efficiency.

Available levels:
- ORT_DISABLE_ALL: No graph optimizations.
- ORT_ENABLE_BASIC: Basic optimizations.
- ORT_ENABLE_EXTENDED: Extended optimizations.
- ORT_ENABLE_ALL: All supported graph optimizations.

### 3. execution_mode
Controls how operations in the computation graph are executed.

- ORT_SEQUENTIAL: Executes graph operations sequentially.
- ORT_PARALLEL: Executes independent graph branches in parallel.

### Key Takeaway
For my TransitNexus CPU benchmark, I will explicitly document the thread count, graph optimization level and execution mode to ensure reproducible measurements.


## Task 3: Loading and Inspecting the ONNX Model

### Model Inspection Results

Model path: models/pothole/best_benchmark.onnx

Available execution providers:
- CoreMLExecutionProvider
- AzureExecutionProvider
- CPUExecutionProvider

Model input details:
- Input name: images
- Input shape: [1, 3, 640, 640]
- Input type: tensor(float)

Active execution provider:
- CPUExecutionProvider

### Key Takeaway
The YOLOv8 ONNX model loaded successfully using ONNX Runtime on my MacBook Air. The model accepts a batch of 1 RGB image with 640x640 resolution and uses CPUExecutionProvider for the current benchmark.


## Task 4: Ultralytics ONNX Export

### 1. Export Command

from ultralytics import YOLO

model = YOLO("best.pt")

model.export(
    format="onnx",
    imgsz=640,
    simplify=True,
    opset=17,
    half=False
)

### 2. Important Export Options

- format="onnx": Exports the PyTorch model into ONNX format.
- imgsz=640: Sets the input image resolution to 640x640.
- simplify=True: Simplifies the ONNX computation graph.
- opset=17: Selects ONNX operator-set version 17 for compatibility.
- half=False: Keeps FP32 precision instead of FP16.

### 3. GPU and Precision Requirements

- Standard FP32 ONNX export can run on CPU.
- Ultralytics supports FP16 ONNX export; suitable hardware and exporter support must be checked.
- FP16 TorchScript export requires a CUDA GPU.
- half=True is a legacy precision flag; quantize=16 is the newer option.

### 4. My TransitNexus Benchmark Choice

I will use:
- Format: ONNX
- Image size: 640x640
- Simplification: Enabled
- Precision: FP32
- Half precision: Disabled

I will retain the existing best_benchmark.onnx model and will not re-export or overwrite it during this session.

### Key Takeaway

Ultralytics converts a trained YOLOv8 PyTorch model into ONNX format using the export() method. Export settings control format, image size, graph simplification, operator compatibility and precision.


---

# S3: ONNX Runtime Graph Optimizations

1. **Basic:** Removes redundant nodes, performs constant folding and applies simple graph simplifications and fusions.
2. **Extended:** Applies advanced operator fusions to supported CPU, CUDA and ROCm execution-provider nodes.
3. **Layout:** Changes supported CPU data layouts, such as NCHW to NCHWc, to improve execution efficiency.
4. **Operator Fusion:** Combines multiple operators into one operation to reduce execution overhead and potentially improve inference latency.

**Optimization levels:**
- ORT_DISABLE_ALL: No graph optimizations.
- ORT_ENABLE_BASIC: Basic optimizations.
- ORT_ENABLE_EXTENDED: Basic + Extended.
- ORT_ENABLE_ALL: Basic + Extended + Layout.


## Session 3 — Graph Optimization A/B Benchmark

### Experimental configuration

- Runtime: ONNX Runtime 1.30.0
- Execution provider: CPUExecutionProvider
- Precision: FP32
- Input size: 640 × 640
- Batch size: 1
- Warm-up iterations: 20
- Timed iterations: 200 per run
- Graph optimization levels: ORT_DISABLE_ALL and ORT_ENABLE_ALL
- Repeated runs: 2 per configuration

### Model graph comparison

| Metric | Original | ORT_ENABLE_ALL |
|---|---:|---:|
| Graph nodes | 233 | 175 |
| File size | 12,265,692 bytes | 12,247,879 bytes |
| Input | images | images |
| Output | output0 | output0 |

Graph node count decreased by approximately 24.9%.

### Model-only benchmark averages

| Metric | ORT_DISABLE_ALL | ORT_ENABLE_ALL |
|---|---:|---:|
| Mean | 36.808 ms | 35.351 ms |
| Median | 34.730 ms | 34.174 ms |
| P95 | 46.562 ms | 42.189 ms |
| P99 | 56.407 ms | 48.325 ms |

Average mean latency decreased by approximately 3.96%.

### End-to-end benchmark averages

Measurement scope: BGR frame to preprocessing, ONNX inference, and NMS.

| Metric | ORT_DISABLE_ALL | ORT_ENABLE_ALL |
|---|---:|---:|
| Mean | 38.378 ms | 35.790 ms |
| Median | 35.994 ms | 34.964 ms |
| P95 | 49.120 ms | 38.851 ms |
| P99 | 61.418 ms | 51.086 ms |

Average mean latency decreased by approximately 6.74%.

### Interpretation

The two-run measurements suggest that ORT_ENABLE_ALL improves both model-only and end-to-end latency. The observed improvement is more pronounced in P95 and P99 latency than in median latency.

Graph optimization also reduced the serialized graph node count from 233 to 175 while preserving the model input and output names.

### Limitations

- Only two benchmark runs were collected per configuration.
- The first ORT_DISABLE_ALL end-to-end run had a maximum latency of 140.834 ms, indicating run-to-run variability.
- The results are preliminary and do not establish statistical significance.
- ORT_ENABLE_ALL serialization emitted a warning that the optimized model may contain hardware-specific optimizations and should be used in the same environment.
- The benchmark used CPUExecutionProvider only; results should not be generalized to other execution providers.

### Conclusion

ORT_ENABLE_ALL showed a promising preliminary latency improvement on this Mac CPU benchmark. Additional repeated measurements under controlled conditions are needed before making a strong performance claim.
