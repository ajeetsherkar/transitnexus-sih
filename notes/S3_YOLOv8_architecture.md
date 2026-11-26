# S3 — YOLOv8 Architecture: NMS Fundamentals

## 1. What is NMS?

NMS stands for Non-Maximum Suppression.

YOLO can predict multiple overlapping bounding boxes for the same
object. NMS removes duplicate detections and keeps the strongest
prediction.

For TransitNexus, the detected object class is Potholes.

## 2. Three Important NMS Concepts

### A. Confidence Threshold

Every predicted bounding box has a confidence score.

The confidence threshold decides which predictions are worth keeping.

Example (confidence threshold = 0.25):

| Detection | Confidence | Decision |
|---|---:|---|
| A | 0.95 | Keep |
| B | 0.82 | Keep |
| C | 0.18 | Reject |

Predictions below the threshold are filtered out before NMS.

### B. IoU Threshold

IoU means Intersection over Union.

It measures the overlap between two bounding boxes.

IoU = Intersection Area / Union Area

Example:
- Box A and Box B overlap heavily.
- Their IoU is 0.90.
- The configured NMS IoU threshold is 0.70.
- The lower-confidence box is suppressed.

A higher IoU means greater overlap.

### C. Per-Class Suppression

NMS is generally applied separately for each object class.

For example, a person detection should not normally suppress
a car detection just because their boxes overlap.

TransitNexus currently has one class:

- Class 0: Potholes

Therefore, all candidate pothole detections are considered
within the same class during class-aware NMS.

## 3. Why Can NMS Take Time on CPU?

1. The detection head can produce thousands of candidate boxes.
2. Confidence filtering removes low-scoring candidates.
3. Remaining boxes are sorted by confidence.
4. NMS calculates box overlaps using IoU.
5. Lower-confidence overlapping boxes are suppressed.

Sorting, indexing and repeated overlap calculations can add
CPU processing overhead, especially when many candidates survive
confidence filtering.

## 4. Why Is NMS Less Straightforward to Batch?

The number of detections that survive NMS can vary by image.

Example:
- Image A: 5 detections
- Image B: 20 detections
- Image C: 2 detections

Neural-network outputs usually have fixed tensor shapes, but
post-NMS detection counts can vary. This makes batching the
final detection outputs less straightforward.

## 5. TransitNexus Model Context

Verified model: models/pothole/best.pt

- Architecture: YOLOv8
- Classes: 1 (Potholes)
- Input tensor: (1, 3, 640, 640)
- Forward output: (1, 5, 8400)
- Detection strides: 8, 16, 32

The forward output represents 8,400 candidate locations.
NMS filters these candidates into final detections.

## 6. Key Takeaway

- Confidence threshold removes weak predictions.
- IoU threshold controls how much overlap is allowed.
- Per-class NMS suppresses duplicate boxes within each class.
- NMS can add CPU overhead because of sorting and overlap calculations.
- The number of final detections can vary from image to image.

**S3 progress:** NMS fundamentals documented.
**Pending:** Architecture pipeline diagram, verified intermediate
tensor shapes, compute-cost estimates, and numerical time-breakdown
prediction.

# 7. Actual YOLOv8 Architecture — Verified Tensor Shapes

The following shapes were collected using forward hooks on the
actual TransitNexus model: models/pothole/best.pt.

Input tensor: (1, 3, 640, 640)

## Backbone — Layers 0–9

| Layer | Operation | Output shape |
|---|---|---|
| 0 | Conv | (1,16,320,320) |
| 1 | Conv | (1,32,160,160) |
| 2 | C2f | (1,32,160,160) |
| 3 | Conv | (1,64,80,80) |
| 4 | C2f | (1,64,80,80) |
| 5 | Conv | (1,128,40,40) |
| 6 | C2f | (1,128,40,40) |
| 7 | Conv | (1,256,20,20) |
| 8 | C2f | (1,256,20,20) |
| 9 | SPPF | (1,256,20,20) |

## Neck — Layers 10–21

| Layer(s) | Operation | Output shape |
|---|---|---|
| 10–12 | Upsample, Concat, C2f | (1,128,40,40) |
| 13–15 | Upsample, Concat, C2f | (1,64,80,80) |
| 16–18 | Conv, Concat, C2f | (1,128,40,40) |
| 19–21 | Conv, Concat, C2f | (1,256,20,20) |

The three detection feature maps are:
- P3: layer 15, (1,64,80,80), 6,400 locations
- P4: layer 18, (1,128,40,40), 1,600 locations
- P5: layer 21, (1,256,20,20), 400 locations

## Detection Head — Layer 22

Detect receives features from layers [15,18,21].

Actual forward output: (1,5,8400)

Total locations = 6,400 + 1,600 + 400 = 8,400.

For this single-class model, the five output values per location
represent four box coordinates and one class score.

NMS subsequently filters candidate boxes to produce final detections.

## Architecture Interpretation

- Backbone extracts visual features and progressively downsamples.
- Neck combines features at multiple spatial scales.
- P3 provides high-resolution features useful for smaller objects.
- P4 provides intermediate-scale features.
- P5 provides lower-resolution, larger-context features.
- Detection head combines the three scales.
- NMS removes low-confidence and duplicate detections.

**Evidence status:** Layer output shapes and final detection output
were directly verified using forward hooks and a 640x640 input.
The diagram is a grouped representation of the actual model layers.

**S3 progress:** Actual architecture tensor shapes verified and documented.

## Compute-Cost Profile — 640x640

### Verified model-level results

- Parameters: 3,011,043 (3.011M)
- THOP total: 4.0958 G MACs
- Conv2d operations: 4.0414 G MACs
- Ultralytics model summary: approximately 8.2 GFLOPs

### Conv2d MAC distribution

| Component | Layers | MACs | Share |
|---|---|---:|---:|
| Backbone | 0-9 | 1.5778 G | 39.04% |
| Neck | 10-21 | 0.9830 G | 24.32% |
| Detection head | 22 | 1.4806 G | 36.63% |
| Total | | 4.0414 G | 99.99% |

### Interpretation and limitations

- Backbone and detection head account for the largest shares of Conv2d MACs.
- Upsampling and concatenation operations are not represented by Conv2d MAC counts.
- MAC percentages are not runtime percentages.
- NMS and ByteTrack require separate timing measurements.
- ByteTrack belongs to the tracking-enabled application path, not the single-model PyTorch benchmark.

Evidence: THOP profiling and PyTorch Conv2d forward hooks at 640x640.


## NMS and ByteTrack Cost Assessment

### NMS — Ultralytics 8.4.142
Source: ultralytics/utils/nms.py

- Confidence filtering removes weak detection candidates.
- IoU threshold controls suppression of overlapping boxes.
- Candidates are filtered and processed before final detections are returned.
- Sorting and box-overlap calculations add CPU overhead.
- More surviving candidates can increase NMS workload.
- TransitNexus pothole model has one class, reducing multi-class complexity.

### ByteTrack — Ultralytics 8.4.142
Source: ultralytics/trackers/byte_tracker.py

Actual update pipeline:
1. Split detections into high- and low-confidence groups.
2. Initialize detection tracks.
3. Predict existing track positions using a Kalman filter.
4. Associate tracks with high-confidence detections.
5. Associate remaining tracks with low-confidence detections using IoU.
6. Update, create, mark lost, and remove tracks.

- More detections and active tracks can increase matching workload.
- Tracking adds per-frame CPU processing.
- ByteTrack is not included in the single-model PyTorch benchmark.

### Compute Assessment — Limitations
- Backbone, neck, and detection-head percentages represent Conv2d MAC shares only.
- They are not measured runtime percentages.
- NMS and ByteTrack have not been independently timed.
- Separate runtime profiling is required before claiming their actual time shares.
- The single-model benchmark excludes video decoding, tracking, GPS, crop saving, and event processing.

Evidence: Installed Ultralytics 8.4.142 source inspection and Conv2d forward-hook profiling.

## Numerical Time-Breakdown Prediction — 640x640

### Measured reference
- PyTorch model-only Run 1: 47.249 ms
- PyTorch model-only Run 2: 46.608 ms
- Combined model-only mean: 46.929 ms/frame
- Model-only path: raw neural-network forward pass, without NMS or tracking.

### Provisional stage estimates

The following estimates allocate model-forward latency according to Conv2d MAC shares. They are not individually measured stage timings.

| Component | Conv2d MAC share | Estimated time |
|---|---:|---:|
| Backbone | 39.04% | 18.32 ms |
| Neck | 24.32% | 11.41 ms |
| Detection head | 36.63% | 17.19 ms |
| Total | 99.99% | 46.92 ms |

### NMS and tracking
- PyTorch model.predict() end-to-end Run 1: 47.044 ms/frame.
- This includes preprocessing, inference, NMS and Python predictor overhead.
- NMS runtime has not been isolated.
- ByteTrack runtime has not been measured.
- ByteTrack is outside the single-model benchmark scope.
- No numerical runtime allocation is claimed for NMS or ByteTrack.

### Interpretation
- Backbone and detection head have the largest Conv2d MAC shares.
- MAC share is only a rough proxy for compute distribution; actual stage latency depends on hardware, memory operations and implementation.
- The estimates must not be presented as measured per-layer latency.
- Further profiling is required to isolate NMS and tracking overhead.

Evidence: Two PyTorch model-only runs, one end-to-end run, THOP profiling and PyTorch Conv2d forward hooks at 640x640.
