# TransitNexus — Pothole Dataset Audit

## Dataset

- Dataset: Multi-Weather Pothole Detection (MWPD)
- Task: Single-class pothole detection
- Class: `Potholes`
- Class ID: `0`
- Dataset location: external to the Git repository
- Training configuration: `ml/data.yaml`

The dataset is kept outside the repository and is not committed to Git.

## Split Statistics

| Split | Images | Bounding Boxes | Class IDs != 0 | Out-of-range | Tiny Boxes |
|---|---:|---:|---:|---:|---:|
| Train | 2,730 | 6,466 | 0 | 0 | 0 |
| Valid | 260 | 573 | 0 | 0 | 0 |
| Test | 97 | 292 | 0 | 0 | 0 |

The audit also checks for missing label files, empty/background label files, malformed rows, and non-numeric label values. No such issues were reported in the completed audit output.

## Label Quality Checks

The audit verified:

- YOLO label rows contain five values where labels are present.
- Class ID is `0` for all audited bounding boxes.
- Bounding-box center coordinates are within `[0, 1]`.
- Bounding-box width and height are within `(0, 1]`.
- No tiny bounding boxes below the configured threshold of `0.0005` box area were reported.
- No missing-label, empty-background, malformed-row, or non-numeric-value warnings were reported.

## Source Leakage Audit

The audit compares the source portion of filenames before `.rf.` between the training split and evaluation splits.

Results:

- Validation images sharing a source with training: **89**
- Test images sharing a source with training: **48**

This is flagged as:

> WARNING: potential source leakage detected

The affected filenames are generated from the dataset audit script and were observed in the completed audit run.

### Interpretation

The validation and test metrics should therefore **not be presented as measurements from a completely source-independent evaluation set**.

The reported metrics remain useful for assessing the trained model on the supplied dataset, but this source-overlap limitation must be disclosed in presentations and documentation.

A future dataset revision should preferably split data by original source/scene before training and evaluation to obtain a cleaner independent test set.

## Audit Script

The audit implementation is:

`ml/audit_dataset.py`

It performs:

1. Image and label enumeration for train/valid/test.
2. Missing and empty-label checks.
3. YOLO five-value row validation.
4. Numeric coordinate validation.
5. Single-class validation.
6. Bounding-box range validation.
7. Tiny-box detection.
8. Filename-based source-overlap detection between train and evaluation splits.

## A1 Evaluation Note

The model was trained and evaluated using the existing MWPD split structure. The source-overlap finding was discovered during the A1 audit and is documented rather than silently corrected after training.

No dataset files were modified as part of this audit.
