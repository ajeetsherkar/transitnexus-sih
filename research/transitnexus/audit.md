# TransitNexus — Day 1 Pipeline Audit

## 1. Repository and environment
- Repository: transitnexus-sih
- Git HEAD at audit start: `e3a86f7052631819925cb5a28f1b3d5bbfa8fde0`
- OS/hardware: macOS 26.5.2 arm64; MacBook Air (Apple M2), 8-core CPU, 8 GB unified memory. Full profile in Sections 11–12.

## 2. Live phone-to-edge pipeline

1. Browser camera capture using `getUserMedia()`.
2. GPS updates using `navigator.geolocation.watchPosition()`.
3. Video frame drawn to canvas and resized to 640 px width.
4. JPEG encoding using `toBlob("image/jpeg", 0.6)`.
5. JSON metadata sent over WebSocket, followed by binary JPEG bytes.
6. Edge server decodes JPEG using NumPy and OpenCV.
7. `process_frame()` runs detection and event processing.
8. Evidence is encoded and event payloads are queued in the local SQLite outbox.
9. Heartbeat is updated and the WebSocket sends boxes, events, GPS and processing time.
10. Uplink worker delivers queued events to the backend; dashboard is downstream.

## 3. Live detector configuration

- Pothole model: `models/pothole/best.pt`
- COCO model: `yolov8n.pt`
- Runtime: Ultralytics YOLO / PyTorch `.pt` models
- Tracker: `bytetrack.yaml`
- Confidence threshold: 0.25
- Ultralytics inference image size: 480
- Two sequential `.track()` calls per frame
- `persist=True` for both model trackers

## 4. Existing edge timing measurement

- Timer starts immediately before `process_frame()` in `edge/server.py`.
- Timer stops immediately after `process_frame()` returns.
- Includes both model detection/tracking calls, timestamp and speed handling, pothole and pedestrian event logic, event-field preparation and box conversion.
- Excludes browser capture, JPEG encoding, WebSocket transfer, server JPEG decoding, evidence encoding, outbox enqueueing, heartbeat update, WebSocket response transmission, backend ingestion and dashboard polling.
- Existing `docs/RESULTS.md` reports approximately 74.7 ms current sample and 76.9 ms rolling median.
- This is edge processing time, not phone-to-dashboard end-to-end latency.

## 5. Browser frame pacing

- Camera request: ideal width 1280 px, rear-facing camera preferred.
- Transmitted frame width: 640 px; height preserves aspect ratio.
- JPEG quality: 0.6.
- Capture loop interval: 500 ms.
- `busy` prevents another frame from being sent while awaiting the current WebSocket response.
- Therefore 500 ms is a nominal scheduling interval, not a guarantee of 2 processed frames per second.

## 6. Separate PyTorch vs ONNX benchmark

Source: `docs/onnx_benchmark.md`

- Hardware: Apple M2 CPU
- Platform: macOS 26.5.2 arm64
- Python: 3.11.13
- PyTorch: 2.14.0
- Ultralytics: 8.4.142
- ONNX Runtime: 1.30.0
- Input: 50 frames, 5 warm-up runs, 640 x 640 inference
- Vehicle YOLOv8n: PyTorch average 33.60 ms; ONNX average 38.12 ms.
- Pothole YOLOv8: PyTorch average 63.25 ms; ONNX average 108.43 ms.
- ONNX was slower in both reported tests.
- This benchmark is separate from live edge timing and must not be directly compared without accounting for differences in model, input size and methodology.

## 7. Documentation discrepancy / multiple workflows

`docs/pipeline.md` describes a batch video workflow with simulated GPS, 5-second congestion aggregation and processed JSON outputs.

The inspected live implementation uses browser camera/GPS streaming, WebSocket frame ingestion, per-frame detection/tracking and event processing.

Treat these as distinct workflows unless further source inspection proves otherwise.

## 8. Unknowns to investigate

- Exact hardware and runtime environment used for the 67–76 ms live measurement.
- Number of frames and warm-up procedure for the live measurement.
- Whether the reported 67–76 ms is based on a controlled repeated benchmark or field observations.
- Exact scope and provenance of the reported 0.2–0.9 FPS field rate.
- Per-stage latency for decoding, both model calls, tracking, event processing and evidence encoding.
- Full phone-to-dashboard latency.
- Accuracy and detection quality under a reproducible validation protocol.

## 9. Distinguishing latency from throughput

- `edge_processing_ms` measures one `process_frame()` execution using `time.perf_counter()`.
- It includes both YOLO tracking calls and event-processing/result-preparation logic.
- It excludes frame waiting, JPEG decoding, optional field recording, evidence encoding, outbox operations and downstream delivery.
- `ai_fps` is calculated as processed frame count divided by elapsed wall-clock time using `time.monotonic()`.
- The FPS window includes frame waiting, JPEG decoding, optional recording and processing; it is not pure model inference FPS.
- `ai_fps` is set to 0.0 until the elapsed window reaches one second.
- Therefore, edge processing latency and observed frame throughput must be reported separately.

## 10. ONNX benchmark methodology audit

Source: `ml/benchmark_onnx.py`

- Loads 50 decoded frames from the same source video and passes the same frame list to both runtimes.
- Uses five warm-up prediction calls per model, then measures 50 prediction calls.
- Warm-up frames are reused in the measured frame list.
- Timer surrounds the complete Ultralytics `model.predict()` call, not only neural-network execution.
- Prediction timing therefore includes the Ultralytics preprocessing, inference and postprocessing pipeline.
- Model loading, video decoding and reporting are excluded from the measured prediction latency.
- Reports average, median, minimum and maximum latency.
- ONNX percentage change is calculated relative to PyTorch average latency; a negative value means ONNX is slower.
- Runtime order is fixed: PyTorch first, ONNX second.
- The script does not report standard deviation, p90/p95 latency or results across independent repeated benchmark runs.
- Device and execution-provider selection are not explicitly specified in this script; verify the actual runtime configuration before reproducing the experiment.
- Existing results are preliminary measurements on the tested Apple M2 CPU, not evidence that one runtime is universally faster.

## 11. Current hardware profile

- Machine: MacBook Air (Mac14,2)
- Chip: Apple M2
- CPU cores: 8 (4 performance + 4 efficiency)
- Unified memory: 8 GB
- Architecture: Apple Silicon
- Hardware profile collected on: 2026-11-21
- Note: This is the current audit machine; historical benchmark environment details are recorded separately.

## 12. Current software environment

- Python: 3.11.13
- Platform: macOS 26.5.2 arm64
- PyTorch: 2.14.0
- Ultralytics: 8.4.142
- ONNX: 1.22.0
- ONNX Runtime: 1.30.0
- OpenCV: 5.0.0
- NumPy: 2.4.6
- PyTorch MPS availability: True
- Available ONNX Runtime providers: CoreMLExecutionProvider, AzureExecutionProvider, CPUExecutionProvider
- Note: Available providers do not prove which provider a previous benchmark actually used. Historical benchmark documentation specifies CPUExecutionProvider.

## 13. Batch inference test — first run (2026-11-21)

Source video: data/raw/videos/mumbra_bhiwandi_01.mp4
Resolution: 1280x720
Frame rate: 30 FPS
Duration: 30 seconds
Frames processed: 900
Model: models/pothole_best.pt
Confidence threshold: 0.25
Extracted events: 78 pothole events
Congestion events: 0

Event JSON inspection:
- Output is a list containing 78 structured events.
- Fields include event_type, confidence, lat, lon, timestamp,
  frame_path, bus_id, route_id and camera_id.
- Confidence minimum: 0.250
- Confidence maximum: 0.627
- Confidence mean: 0.3336
- Confidence median: 0.298
- 40/78 events have confidence below 0.30.
- 72/78 events have confidence below 0.50.
- There are 76 unique timestamps among 78 events.

Timestamp finding:
- format_timestamp() uses datetime.fromtimestamp(seconds, UTC).
- Video timestamps are calculated as frame_number / FPS.
- Therefore timestamps are video-relative elapsed seconds represented
  as dates beginning on 1970-01-01, not actual recording timestamps.

GPS finding:
- Batch inference calls get_gps_at_timestamp() from tools/gps_simulator.py.
- Coordinates are simulated/interpolated along a predefined route,
  not obtained from actual GPS metadata in the source video.

Limitations:
- Extracted events are not independently verified ground truth.
- Confidence scores alone do not establish detection precision.
- Batch inference output contains no per-frame timing measurement.
- Batch inference is separate from the live phone-to-edge pipeline.

## 14. Open research questions

Unknowns requiring investigation:
1. Does the 67–76 ms edge processing measurement remain stable across repeated runs?
2. What are the p50 and p95 edge processing times under controlled conditions?
3. How much time is spent in the pothole model versus the COCO model?
4. How do CPU PyTorch and ONNX Runtime compare under identical inputs?
5. Does CoreMLExecutionProvider improve inference performance on Apple M2?
6. What is the actual end-to-end phone-to-dashboard latency?
7. How do confidence thresholds affect precision and recall on labelled data?
8. How much do event generation and ByteTrack contribute to processing time?
9. Why does README field throughput (0.2–0.9 FPS) differ from the approximately 2 FPS capture/response rate in docs/RESULTS.md?

Three initial benchmark questions:
1. What are the latency distributions (p50, p95) of the live edge processing pipeline across repeated runs?
2. Under identical model inputs and hardware, how do PyTorch and ONNX Runtime CPU compare in latency and accuracy?
3. Can stage-level profiling identify whether model inference, tracking, or event processing is the main performance bottleneck?

## 15. Explicit pipeline stage-to-file mapping

LIVE PHONE-TO-EDGE PIPELINE

1. Frame source:
   edge/static/client.html
   Browser camera capture using getUserMedia().

2. Client preprocessing and transmission:
   edge/static/client.html
   Canvas resize to 640 px width, JPEG encoding, metadata JSON
   and binary frame transmission over WebSocket.

3. Frame reception and decoding:
   edge/server.py
   WebSocket receives metadata and JPEG bytes; OpenCV decodes
   the image before processing.

4. Model loading:
   edge/detector.py
   Loads the pothole and COCO YOLO PyTorch .pt models.

5. Model inference and tracking:
   edge/detector.py
   Calls YOLO.track() sequentially for pothole and COCO models.
   ByteTrack is selected using bytetrack.yaml.

6. NMS and model postprocessing:
   Ultralytics YOLO inference/tracking path called from
   edge/detector.py. NMS is handled within the Ultralytics
   inference pipeline; no separate project NMS stage was
   identified in the inspected live detector code.

7. Event engine:
   edge/events.py
   Live event confirmation and tracking logic.
   edge/server.py invokes process_frame(), which calls
   detector.detect() and the event engine.

8. Evidence generation and uplink:
   edge/server.py and edge/uplink.py
   Evidence encoding, SQLite outbox enqueue, heartbeat
   updates and asynchronous backend delivery.

9. Backend ingestion:
   backend/main.py, backend/routes.py, backend/db.py
   FastAPI ingestion, routing and database operations.

10. Dashboard:
    dashboard/app.py and dashboard/api.py
    Dashboard application and API integration.

SEPARATE ONNX BENCHMARK PATH

- ml/benchmark_onnx.py: benchmark runner.
- models/pothole_best.pt and models/pothole_best.onnx:
  pothole model formats.
- yolov8n.pt and yolov8n.onnx:
  vehicle model formats.
- docs/onnx_benchmark.md: documented benchmark methodology
  and historical results.

Important distinction:
The live edge detector uses PyTorch .pt models. The ONNX
benchmark is a separate offline experiment. The two paths
must not be treated as one identical pipeline.

## 16. Complete timing-reference classification

Source inventory:
eth_prep/notes/timing_grep.txt

Actual live processing measurement:
- edge/server.py:591-600
- time.perf_counter() surrounds the run_in_threadpool()
  call to process_frame().
- Measures process_frame() execution in milliseconds.
- Includes both sequential model detect/track calls and
  event-engine processing inside process_frame().
- Excludes JPEG decoding, evidence encoding, outbox enqueue,
  heartbeat update and WebSocket response transmission.

Live throughput measurement:
- edge/server.py:522, 604-611
- time.monotonic() measures elapsed wall-clock time.
- ai_fps is calculated as frame_count / elapsed when the
  measurement window reaches at least one second.
- This is frame throughput, not the inverse of edge_processing_ms.
- The first value may be zero before the first window completes.

Offline model benchmark:
- ml/benchmark_onnx.py:71-79
- time.perf_counter() surrounds each model.predict() call.
- Model initialization is outside the timer.
- Five warm-up predictions are performed before measurement.
- The measured calls include Ultralytics prediction processing.
- Reports average, median, minimum and maximum.
- Does not report p95 or p99 in the inspected implementation.

Video metadata and derived timing:
- edge/run_inference.py uses video FPS to calculate duration,
  frame timestamps and density-window frame counts.
- edge/run_a2_demo.py reads source-video FPS and calculates
  frame-relative timestamps.
- These references do not themselves measure inference latency.

Simulation clock:
- tools/simulate_fleet.py uses time.monotonic() for simulation
  duration, elapsed simulation time and heartbeat scheduling.
- tools/simulate_fleet.py contains a fixed ai_fps value of 2.0
  in a simulated payload; this is not measured throughput.

Data propagation and test references:
- edge/uplink.py carries ai_fps through heartbeat state and
  payload construction.
- backend/schemas.py defines the ai_fps field.
- backend/tests/test_api.py supplies ai_fps as test data.
- These are not independent performance measurements.

Inventory conclusion:
- The Python timing grep was saved in eth_prep/notes/timing_grep.txt.
- Actual inference/processing timers were identified in
  edge/server.py and ml/benchmark_onnx.py.
- Other matches primarily represent video metadata,
  simulation clocks, fixed values or data propagation.

## 17. Historical A7 measurement — evidence verification

Source: docs/RESULTS.md, A7 — Edge Processing Measurement
Historical measurement date: 2026-09-20
Test: Live browser camera to Edge WebSocket inference
Bus ID: TN-BUS-001

Documented measurements:
- Capture/response rate: approximately 2.0 FPS.
- Current edge processing sample: 74.7 ms.
- Rolling median: 76.9 ms/frame.
- Capture width: 640 pixels.
- YOLO inference image size: 480.

Verified measurement scope:
- edge/server.py starts time.perf_counter() immediately before
  the run_in_threadpool(process_frame, ...) call.
- process_frame() calls detector.detect() and the event engine.
- Therefore model detection/tracking and event-engine processing
  are inside the timed interval.
- JPEG decoding, evidence encoding, outbox enqueue, heartbeat
  updates and WebSocket response transmission are outside it.

Documentation discrepancy:
- docs/RESULTS.md says event creation is outside the measurement.
- Source inspection shows event-engine processing occurs inside
  process_frame(), which is timed.
- This statement requires correction or clarification.

Historical experimental details not established by the inspected
A7 results document:
- Exact CPU/GPU/device used for the September 20 measurement.
- Number of warm-up frames.
- Number of measured frames/samples.
- Total measurement duration.
- Distribution beyond the reported current sample and rolling median.
- Exact method used to calculate the approximately 2.0 FPS
  capture/response rate.

These missing details are marked UNKNOWN, not inferred from the
current development machine or the separate ONNX benchmark.

Status:
The historical 74.7 ms sample and 76.9 ms rolling median are
documented results, but the experiment is not fully reproducible
from the published methodology.

## 18. Multi-bus fleet testing and dashboard evidence

Developer-reported test:
- Successfully executed a 10-bus fleet simulation.
- Bus locations were visualized simultaneously on a shared
  Kopargaon map.
- The dashboard retains last-known bus locations.
- Individual bus information includes speed, heading,
  GPS accuracy and camera identifier.

Demonstrated dashboard capabilities:
- Fleet monitoring and online/offline status.
- Shared geographical visualization of bus markers.
- Live and simulated bus marker identification.
- Individual bus telemetry.
- Incident alerts and aggregation.
- Incident details, contributing bus information and evidence images.

Available screenshot evidence demonstrates:
- Fleet dashboard with bus markers on the map.
- Selected bus information and telemetry.
- Incident detail view with confidence, timeline,
  contributing bus and evidence image.
- Fleet alert panel and incident counts.

Evidence note:
The screenshots are supporting evidence of the dashboard
and its functionality. The 10-bus simultaneous test is
recorded separately as a developer-reported test.

