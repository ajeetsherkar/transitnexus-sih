# TransitNexus Benchmark Experiment Plan

## 1. Research Question

How do runtime, precision, input size, batch size and CPU thread
count affect latency, throughput and detection accuracy of the
TransitNexus pothole detection pipeline on the available hardware?

## 2. Variables Under Investigation

- Runtime: PyTorch vs ONNX Runtime (ORT)
- ORT graph optimisations: enabled vs disabled
- Precision: FP32, FP16 and INT8 where supported
- Input resolution: 320, 416 and 640
- Batch size: 1, 4 and 8
- CPU thread count: 1, 2, 4 and 8

## 3. Experimental Controls

The following conditions define the baseline experiment.

| Control | Fixed setting |
|---|---|
| Benchmark video | data/benchmark/bench_clip_fixed.mp4 |
| Number of source frames | 200 |
| Video resolution | 1280 x 720 |
| Video frame rate | 30 FPS |
| Video duration | Approximately 6.67 seconds |
| Detection task | Pothole detection |
| PyTorch model | models/pothole/best.pt |
| ONNX model | models/pothole/best_benchmark.onnx |
| Baseline inference size | 640 x 640 |
| Baseline precision | FP32 |
| PyTorch device | CPU |
| ORT execution provider | CPUExecutionProvider |
| Confidence threshold | 0.25 |
| NMS IoU threshold | 0.70 |
| Hardware | Apple M2 MacBook Air |
| Python environment | Same Python environment for all comparable runs |
| Input frames | Same decoded frames for both runtimes |

### Environmental Controls

- Use the same MacBook Air for all experiments.
- Connect the laptop to power before benchmarking.
- Close unnecessary background applications.
- Use the same Python environment and package versions.
- Avoid changing model weights during the experiment.
- Record software versions and hardware details.
- Change only the variable being investigated.
- Use identical input frames and equivalent preprocessing and
  postprocessing for runtime comparisons.
- Record any unsupported configuration rather than silently
  substituting another configuration.

## 4. Evaluation Metrics

| Metric | Meaning | Unit |
|---|---|---|
| Mean latency | Average processing time per frame | ms/frame |
| Standard deviation | Variation in frame latency | ms |
| Median latency (p50) | Middle frame latency | ms/frame |
| p95 latency | Latency below which 95% of observations fall | ms/frame |
| p99 latency | Latency below which 99% of observations fall | ms/frame |
| Throughput | Frames processed per second | frames/s |
| Peak memory | Maximum memory used during the experiment | MB |
| Model loading time | Time needed to load the model/runtime | seconds |
| mAP@50 | Detection accuracy at IoU threshold 0.50 | percentage |
| Detection consistency | Agreement between matched PyTorch and ORT boxes | IoU |

### Accuracy Evaluation

- Calculate mAP@50 on the labelled validation dataset using the
  corresponding ground-truth annotations.
- Keep the validation dataset and evaluation settings fixed.
- Do not treat the 200-frame benchmark video as a labelled
  validation set unless ground-truth annotations exist for it.
- Report unavailable accuracy measurements as not evaluated.
- Detection consistency is not a substitute for ground-truth accuracy.

### Latency Measurement Scope

The primary end-to-end per-frame latency timer will cover:

1. Image preprocessing and input preparation.
2. Model inference.
3. Detection postprocessing, including confidence filtering
   and non-maximum suppression (NMS).

The timer will exclude:

- Video file decoding and frame extraction.
- Model loading and initialisation.
- Warm-up iterations.
- Displaying, drawing or saving annotated frames.

For batch experiments, report both total batch latency and
per-frame latency (batch latency divided by batch size).

If inference-only latency is measured separately, report it
as a separate metric and do not mix it with end-to-end latency.

### Measurement Rules

- Perform 20 warm-up iterations before timed measurements.
- Collect at least 200 timed iterations per configuration.
- Report mean, standard deviation, p50, p95 and p99.
- Calculate throughput as total timed frames divided by total
  measured processing time.
- Measure model loading time separately.
- Record peak memory separately from latency.
- Use IoU >= 0.50 for bounding-box matching.
- Preserve raw measurements for every run.

## 5. Experiment Matrix

Unless explicitly stated otherwise, E4-E7 use ONNX Runtime CPU,
FP32 precision, 640 input resolution, batch size 1 and the
baseline CPU thread setting. Each experiment changes only its
specified independent variable while keeping the other settings fixed.

For E4, precision configurations are compared against the FP32
baseline. For E5, E6 and E7, the corresponding baseline setting
is changed while all other settings remain fixed.

| Experiment | Variable and configurations | Fixed settings | Runs |
|---|---|---|---|
| E1 | PyTorch CPU baseline, FP32 | 640 input, batch 1, CPU, same 200 frames | 3 process launches |
| E2 | ORT CPU, FP32 | Same model, frames, 640 input, batch 1 | 3 process launches |
| E3 | ORT graph optimisations ON vs OFF | FP32, 640 input, batch 1, CPU provider | 3 launches per configuration |
| E4 | Precision: FP32, FP16, INT8 where supported | Same runtime, model task, frames and input size | 1 screening launch per configuration; repeat selected configurations 3 times |
| E5 | Resolution: 320, 416, 640 | Same runtime, precision, batch 1 and threads | 1 screening launch per configuration; repeat selected configurations 3 times |
| E6 | Batch size: 1, 4, 8 | Same runtime, precision, resolution and threads | 1 screening launch per configuration; repeat selected configurations 3 times |
| E7 | CPU threads: 1, 2, 4, 8 | Same runtime, precision, resolution and batch size | 1 screening launch per configuration; repeat selected configurations 3 times |

### Experiment Execution Rules

- E1 is the PyTorch CPU baseline.
- E2 compares ORT CPU against the PyTorch baseline.
- E3 compares ORT graph optimisations enabled and disabled.
- E4 investigates supported precision configurations.
- E5 investigates input resolution.
- E6 investigates batch size.
- E7 investigates CPU thread count.
- Use 20 warm-up iterations and at least 200 timed iterations
  for each configuration.
- Run each headline configuration in three separate processes.
- Use one screening launch for exploratory configurations, then
  repeat selected configurations in three separate processes.
- Keep all other settings fixed when changing one variable.
- Record unsupported configurations and their reasons.
- Check detection consistency and validation accuracy when
  changing precision or resolution.
- Do not compare results from different hardware as equivalent.

## 6. Stop Rules and Failure Conditions

An experiment will be stopped or marked invalid under the
following conditions:

1. Stop if the model fails to load or produces invalid outputs.
2. Stop if the benchmark video cannot provide all expected
   200 source frames.
3. Stop if inference produces runtime errors or non-finite
   latency values.
4. Stop if 20 warm-up iterations cannot be completed.
5. Mark a run incomplete if fewer than 200 timed iterations
   are collected.
6. Stop if the laptop shows signs of thermal or system instability.
7. Stop if memory usage becomes unsafe or the system becomes
   unresponsive.
8. Repeat a run if unexpected background activity significantly
   affects measurements.
9. Mark unsupported runtime, precision, batch-size or thread
   configurations as unsupported.
10. Do not silently discard failed runs or unusual measurements.
11. Record the reason for every stopped, repeated or invalid run.
12. Do not report incomplete experiments as successful results.

### Result Validity and Reporting

- Use three separate process launches for headline configurations.
- Report each process result and the aggregate results.
- Investigate unusually large latency variations.
- Keep raw measurements for later analysis.
- Report failed runs, unsupported configurations and limitations.
- Do not remove outliers without recording and justifying the reason.
- Do not claim accuracy improvements without validation-set
  ground-truth evaluation.

## 7. Research Hypotheses

The following hypotheses will be evaluated through controlled
experiments. They are predictions and may be rejected by the results.

### H1 – Runtime Comparison

ONNX Runtime CPU will achieve lower median latency (p50) than
PyTorch CPU for the same model and input frames.

### H2 – Precision and Accuracy

INT8 quantisation will cause a larger reduction in validation
mAP@50 than FP16 precision compared with the FP32 baseline,
where these precision modes are supported.

### H3 – Preprocessing Contribution

Image preprocessing will account for a measurable share of the
total end-to-end detection pipeline latency.
