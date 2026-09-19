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
