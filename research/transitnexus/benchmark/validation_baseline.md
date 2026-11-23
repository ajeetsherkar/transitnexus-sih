# Pothole Detection – Validation Baseline

## 1. Purpose

Record the existing PyTorch model's validation performance before
conducting controlled runtime benchmark experiments.

These measurements are the validation baseline. They are not
new benchmark latency results.

## 2. Model and environment

- Model: YOLOv8n pothole detector
- Model file: `models/pothole/best.pt`
- Dataset configuration: `ml/data.yaml`
- Dataset split: `valid`
- Input image size: 416
- Device: Apple M2 MPS
- Python: 3.11.13
- PyTorch: 2.14.0
- Ultralytics: 8.4.142

## 3. Validation dataset

| Property | Value |
|---|---:|
| Validation images | 260 |
| Ground-truth instances | 573 |
| Background images | 0 |
| Corrupt images | 0 |

## 4. Validation metrics

| Metric | Result |
|---|---:|
| Precision | 0.7878 |
| Recall | 0.6609 |
| mAP@50 | 0.7488 |
| mAP@50–95 | 0.3676 |

The validation output also reported:

- Preprocessing: 0.1 ms/image
- Inference: 2.0 ms/image
- Postprocessing: 4.3 ms/image

These are Ultralytics validation speed figures. They must not be
treated as the controlled end-to-end latency measurements defined
in `BENCH_PLAN.md`.

## 5. Evaluation configuration

- Evaluation method: Ultralytics validation (`model.val`)
- Split: `val`
- Image size: 416
- Device: MPS
- Results directory:
  `runs/detect/runs/ssrf_validation_baseline`

## 6. Dataset audit limitations

The dataset audit identified potential source overlap:

- 89 validation images share source identifiers with training.
- 48 test images share source identifiers with training.

This is a potential source-leakage concern based on filename-derived
source identifiers. It has not been independently confirmed as
duplicate-image leakage.

The limitation must be considered when interpreting validation
and test metrics.

## 7. Interpretation

The model achieved 0.7488 mAP@50 on the validation split.

These results establish an existing accuracy reference for future
runtime and precision experiments.

Any comparison between FP32, FP16, INT8, or different runtimes
must use equivalent evaluation data and settings.

No new accuracy improvement is claimed by this record.
