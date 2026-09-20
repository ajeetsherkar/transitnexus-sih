# TransitNexus — Pothole Detection Model Card

## Model Overview

- Project: TransitNexus
- Model: YOLOv8n
- Task: Single-class pothole object detection
- Class: `Potholes`
- Number of classes: 1
- Base model: `yolov8n.pt`
- Training image size: `416`
- Training epochs: `40`
- Batch size: `8`
- Training device: Apple M2 MPS
- Dataset configuration: `ml/data.yaml`
- Trained weights: `models/pothole/best.pt` after packaging
- Current training artifact: `runs/detect/runs/pothole_v1/weights/best.pt`
- Packaged model artifact: `models/pothole/best.pt`
- Packaged model SHA-256: `4a1eba894263fea7874eb4ea9e4dd3887bcb4e8d2bed83ccaa098f5d3e35608f`

## Training

The model was fine-tuned from the pretrained YOLOv8n model on the Multi-Weather Pothole Detection (MWPD) dataset.

Training configuration:

- Epochs: 40
- Image size: 416 × 416
- Batch size: 8
- Optimizer/scheduler: Ultralytics default configuration
- Early stopping patience: 8
- Device: Apple M2 MPS

A 3-epoch smoke run was completed before the full training run to verify the training pipeline.

## Evaluation Results

### Validation Set

- Images: 260
- Ground-truth instances: 573
- Precision: **0.788**
- Recall: **0.661**
- mAP50: **0.749**
- mAP50-95: **0.368**
- Inference: approximately **1.6 ms/image** in the final validation run

### Test Set

- Images: 97
- Ground-truth instances: 292
- Precision: **0.782**
- Recall: **0.674**
- mAP50: **0.743**
- mAP50-95: **0.384**
- Inference: approximately **4.4 ms/image** in the test evaluation run

The measured inference speed is hardware- and workload-dependent and should not be interpreted as an end-to-end phone-to-dashboard latency.

## Confidence Threshold

The validation F1 curve was inspected after training.

- F1 peak: **0.7219**
- Confidence at F1 peak: **0.4364**
- Starting event confidence threshold for A2: **0.44**

The `0.44` value is a starting operating threshold derived from the validation F1 peak. It is not treated as a universally optimal threshold.

A2 event logic will additionally use temporal evidence rather than firing a pothole event from a single detection alone.

## Test-Set Prediction Review

All **97 test images** were run through the trained model at confidence `0.44`.

For an additional qualitative/object-level review using an IoU threshold of `0.50`, the prediction comparison produced:

- True positives: **183**
- False positives: **56**
- False negatives: **109**

These counts are used as a supplementary review of the saved predictions and are not a replacement for the official Ultralytics precision/recall/mAP metrics above.

### Representative Examples

The following examples were selected from the objective prediction review:

1. `19_jpg.rf.c0972876ad058389d3ec2943deae367d.jpg`
   - Strong detection candidate
   - TP: 8
   - FP: 1
   - FN: 2

2. `42_jpg.rf.696a9b420c428a2baee8e04090fa6167.jpg`
   - False-positive candidate
   - TP: 0
   - FP: 19
   - FN: 1

3. `266_jpg.rf.ae8b01c2b6d63ee1d9f2d32c233339b8.jpg`
   - Missed-detection candidate
   - TP: 4
   - FP: 1
   - FN: 12

4. `605_jpg.rf.1f9762a5458c14c9d0f2607704a4fc6c.jpg`
   - Missed-detection candidate
   - TP: 5
   - FP: 1
   - FN: 11

These examples are qualitative evidence from the test-set review. They should not be presented as formal per-weather or per-size benchmark categories.

## Dataset Limitation

The dataset audit detected potential source overlap:

- Validation images sharing a source with training: **89**
- Test images sharing a source with training: **48**

Therefore, the validation and test results should not be described as coming from completely source-independent evaluation sets.

This limitation is documented in `docs/DATASET_AUDIT.md`.

## Intended Use

The model is intended as the pothole detection component of the TransitNexus edge-AI pipeline.

The planned A2 pipeline uses:

1. Frame capture from a bus-mounted/mobile camera.
2. YOLO pothole detection.
3. Tracking across frames.
4. Temporal event logic.
5. Confidence filtering.
6. Event generation for the TransitNexus backend.
7. Evidence-frame generation where applicable.

The model is therefore one component of the complete incident-detection system rather than a standalone road-condition authority.

## Limitations

Known limitations include:

- Potential train/evaluation source overlap in the supplied dataset.
- The test set contains only 97 images.
- Performance can vary with lighting, weather, camera angle, motion blur, road surface, and pothole size.
- The reported MPS inference measurements are not representative of all deployment hardware.
- Object detection confidence does not directly represent real-world severity.
- A detection alone does not establish that a pothole is safe/unsafe to drive over.
- The model should be combined with temporal and contextual logic before generating operational events.

## Reproducibility

Important project files:

- `ml/data.yaml`
- `ml/train_pothole.py`
- `ml/evaluate_pothole.py`
- `ml/audit_dataset.py`

Training artifact before packaging:

`runs/detect/runs/pothole_v1/weights/best.pt`

The dataset itself remains external to the repository.

## A2 Handoff

Recommended initial pothole detection confidence threshold:

**0.44**

This value should be treated as the initial operating point for A2's tracking and temporal event logic. Field testing in later Day A sessions should be used to measure false positives, missed detections, and operational behavior before making any claim about deployment performance.
