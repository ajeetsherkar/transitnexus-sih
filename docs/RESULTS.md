# TransitNexus Round 3 Results

## S1.4 — Spatio-Temporal Deduplication

### Round-2 Replay Measurement

**Dataset:** Replayed Round-2 data  
**Source:** `data/processed/events.json`  
**Replay size:** 2,606 raw reports

The complete Round-2 event set was replayed through the TransitNexus S1.4 deduplication engine using an isolated temporary SQLite database.

| Metric | Result |
|---|---:|
| Raw Round-2 reports | 2,606 |
| Reports supported by S1.4 dedup | 11 |
| Deduplicated incidents | 2 |
| Reports linked to incidents | 11 |
| Raw-to-incident reduction | 99.92% |

The S1.4 deduplication engine currently processes `pothole` and `pedestrian_risk` events. Other Round-2 event types remain raw reports and are not included in incident deduplication.

### Interpretation

The replay demonstrates that multiple reports of the same supported incident can be consolidated into a single incident rather than being treated as independent incidents.

**Important:** This is a replay of Round-2 data, not a live-production measurement. The 99.92% raw-to-incident reduction compares all 2,606 raw reports with the resulting 2 deduplicated incidents and should not be interpreted as a pothole-detection accuracy or model-performance metric.

### Verification

- Dedup TDD tests: **7/7 passed**
- Existing API regression tests: **8/8 passed**
- Combined backend tests: **15/15 passed**
- Round-2 replay measurement: **PASS**

## A7 — Edge Processing Measurement

### Live Edge Measurement

**Date:** 2026-09-20

**Test:** Live browser camera → Edge WebSocket inference using `TN-BUS-001`

| Metric | Result |
|---|---:|
| Capture / response rate | ~2.0 FPS |
| Edge processing current sample | 74.7 ms |
| Edge processing rolling median | **76.9 ms/frame** |
| Inference image width | 640 px capture / 480 px YOLO inference |

The edge processing measurement covers the `process_frame()` execution path on the Edge server. It does **not** represent full phone-to-dashboard latency because network transport, backend ingestion, event creation, and dashboard polling are outside this measurement.

### A7 Status

- Live Edge connection: **PASS**
- GPS active: **PASS**
- AI detections returned to phone: **PASS**
- Edge processing measurement: **PASS**
- Median edge processing time: **76.9 ms/frame**
- Full phone-to-dashboard latency measurement: **PENDING**
- Physical A5 field-test reality-check set: **PENDING**

No confidence threshold, hit-count threshold, model weights, or image-size inference setting was changed during this measurement. Evidence-based tuning remains pending the physical field-test reality-check set.
