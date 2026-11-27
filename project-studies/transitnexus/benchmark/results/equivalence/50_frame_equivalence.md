# PyTorch vs ONNX — 50-frame equivalence

Date: 2026-11-27T22:34:35

## Configuration
- Frames: 50 (first 50 sequential video frames)
- Input: 640 x 640, FP32
- Confidence: 0.25
- NMS IoU: 0.7
- Class-agnostic NMS: False
- Maximum detections: 300
- Bounding-box tolerance: 2.0 pixels
- Confidence tolerance: 0.01

## Aggregate results
- PyTorch detections: 8
- ONNX detections: 8
- Matched detections: 8
- Unmatched PyTorch detections: 0
- Unmatched ONNX detections: 0
- Maximum matched box error: 0.000031 px
- Maximum matched confidence error: 0.00000158
- Minimum matched IoU: 0.99999869

## Frame results

| Frame | PT | ONNX | Matched | Unmatched PT | Unmatched ONNX | Max box error (px) | Max confidence error | Result |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 2 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 3 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 4 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 5 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 6 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 7 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 8 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 9 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 10 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 11 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 12 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 13 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 14 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 15 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 16 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 17 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 18 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 19 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 20 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 21 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 22 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 23 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 24 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 25 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 26 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 27 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 28 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 29 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 30 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 31 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 32 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 33 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 34 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 35 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 36 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 37 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 38 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 39 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 40 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 41 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 42 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 43 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 44 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 45 | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 46 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000001 | PASS |
| 47 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000000 | PASS |
| 48 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000002 | PASS |
| 49 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000001 | PASS |
| 50 | 1 | 1 | 1 | 0 | 0 | 0.0000 | 0.000001 | PASS |

## Final assessment

Overall result: PASS

Matching uses greedy highest-IoU pairing within the same class. Unmatched detections are counted as mismatches. This is a numerical equivalence check, not an accuracy evaluation.
