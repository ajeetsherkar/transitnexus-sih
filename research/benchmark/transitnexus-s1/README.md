# TransitNexus – Benchmark Research

This directory contains the project-specific research records and
experimental plan for evaluating pothole detection performance.

## Files

| File | Purpose |
|---|---|
| `BENCH_PLAN.md` | Research question, controls, experiment matrix, metrics and run protocol |
| `validation_baseline.md` | Existing PyTorch validation results and dataset limitations |
| `model_provenance.md` | Selected model files, checksums and ONNX verification |

## Related project documentation

- Dataset audit: [`docs/DATASET_AUDIT.md`](../../../docs/DATASET_AUDIT.md)
- Historical ONNX benchmark: [`docs/onnx_benchmark.md`](../../../docs/onnx_benchmark.md)
- Model card: [`docs/MODEL_CARD.md`](../../../docs/MODEL_CARD.md)
- Dataset configuration: [`ml/data.yaml`](../../../ml/data.yaml)
- Dataset audit script: [`ml/audit_dataset.py`](../../../ml/audit_dataset.py)

## Benchmark input

The selected local benchmark video is:

`data/benchmark/bench_clip_fixed.mp4`

It is intentionally excluded from Git through the existing `data/`
ignore rule. The video contains 200 frames at 1280 × 720 and 30 FPS.

## Important distinctions

- The validation baseline is an existing accuracy evaluation using
  MPS at image size 416.
- The controlled runtime benchmark is a separate experiment defined
  in `BENCH_PLAN.md`.
- Historical ONNX benchmark results use older model files and a
  different video/configuration.
- The dataset audit identified potential source overlap between
  training and validation/test splits. This limitation must be
  disclosed when interpreting results.

## Current experiment status

The benchmark plan and required model artifacts are documented.
The controlled latency experiment has not yet been run.

Results must be added only after the corresponding experiment has
actually been executed and verified.
