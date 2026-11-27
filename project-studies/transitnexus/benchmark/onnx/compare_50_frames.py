import cv2
import csv
import numpy as np
import torch
import onnxruntime as ort

from pathlib import Path
from datetime import datetime
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox
from ultralytics.utils import nms

ROOT = Path.home() / "transitnexus-sih"
MODEL_PATH = ROOT / "models/pothole/best.pt"
ONNX_PATH = ROOT / "models/pothole/best_benchmark.onnx"
VIDEO_PATH = ROOT / "data/benchmark/bench_clip_fixed.mp4"

OUT = Path("project-studies/transitnexus/benchmark/results/equivalence")
OUT.mkdir(parents=True, exist_ok=True)

IMGSZ = 640
CONF = 0.25
IOU = 0.70
MAX_DET = 300
FRAME_COUNT = 50
BOX_TOLERANCE = 2.0
CONF_TOLERANCE = 0.01


def preprocess(frame):
    transform = LetterBox(
        new_shape=(IMGSZ, IMGSZ),
        auto=False,
        scale_fill=False,
        scaleup=True,
        center=True,
        stride=32,
        padding_value=114,
        interpolation=cv2.INTER_LINEAR,
    )
    image = transform(image=frame)
    image = image[:, :, ::-1].transpose(2, 0, 1)
    image = np.ascontiguousarray(image[None], dtype=np.float32)
    return image / 255.0


def get_detections(prediction):
    return nms.non_max_suppression(
        prediction.clone(),
        conf_thres=CONF,
        iou_thres=IOU,
        classes=None,
        agnostic=False,
        multi_label=False,
        max_det=MAX_DET,
        nc=1,
        end2end=False,
    )[0].detach().cpu().numpy()


def box_iou(a, b):
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def match_detections(pt, onnx):
    unmatched = set(range(len(onnx)))
    matches = []

    for i, p in enumerate(pt):
        candidates = []

        for j in unmatched:
            o = onnx[j]
            if int(p[5]) != int(o[5]):
                continue

            overlap = box_iou(p[:4], o[:4])
            coordinate_error = float(np.max(np.abs(p[:4] - o[:4])))
            candidates.append((overlap, coordinate_error, j))

        if not candidates:
            continue

        candidates.sort(key=lambda item: (-item[0], item[1]))
        overlap, error, j = candidates[0]
        unmatched.remove(j)

        matches.append({
            "pt_index": i,
            "onnx_index": j,
            "iou": overlap,
            "box_error": error,
            "confidence_error": float(abs(p[4] - onnx[j][4])),
        })

    return matches, len(pt) - len(matches), len(unmatched)


def main():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(MODEL_PATH)
    if not ONNX_PATH.is_file():
        raise FileNotFoundError(ONNX_PATH)
    if not VIDEO_PATH.is_file():
        raise FileNotFoundError(VIDEO_PATH)

    model = YOLO(str(MODEL_PATH))
    session = ort.InferenceSession(
        str(ONNX_PATH),
        providers=["CPUExecutionProvider"],
    )

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        raise RuntimeError("Could not open benchmark video")

    rows = []
    total_pt = 0
    total_onnx = 0
    total_matched = 0
    total_unmatched_pt = 0
    total_unmatched_onnx = 0
    all_box_errors = []
    all_conf_errors = []
    all_ious = []

    try:
        for frame_index in range(FRAME_COUNT):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(
                    f"Video ended before frame {FRAME_COUNT}; "
                    f"only reached {frame_index} frames"
                )

            tensor_np = preprocess(frame)
            tensor = torch.from_numpy(tensor_np)

            with torch.inference_mode():
                pt_output = model.model(tensor)
                if isinstance(pt_output, (tuple, list)):
                    pt_output = pt_output[0]

            ort_output = session.run(
                [output_name],
                {input_name: tensor_np},
            )[0]

            if tuple(pt_output.shape) != tuple(ort_output.shape):
                raise RuntimeError(
                    f"Raw output shape mismatch at frame {frame_index}"
                )

            pt_detections = get_detections(pt_output)
            onnx_detections = get_detections(
                torch.from_numpy(ort_output)
            )

            matches, missing_pt, missing_onnx = match_detections(
                pt_detections, onnx_detections
            )

            box_errors = [m["box_error"] for m in matches]
            conf_errors = [m["confidence_error"] for m in matches]
            ious = [m["iou"] for m in matches]

            total_pt += len(pt_detections)
            total_onnx += len(onnx_detections)
            total_matched += len(matches)
            total_unmatched_pt += missing_pt
            total_unmatched_onnx += missing_onnx

            all_box_errors.extend(box_errors)
            all_conf_errors.extend(conf_errors)
            all_ious.extend(ious)

            box_max = max(box_errors, default=0.0)
            conf_max = max(conf_errors, default=0.0)
            iou_min = min(ious, default=1.0)

            frame_pass = (
                missing_pt == 0
                and missing_onnx == 0
                and box_max <= BOX_TOLERANCE
                and conf_max <= CONF_TOLERANCE
            )

            rows.append({
                "frame": frame_index,
                "pytorch_detections": len(pt_detections),
                "onnx_detections": len(onnx_detections),
                "matched": len(matches),
                "unmatched_pytorch": missing_pt,
                "unmatched_onnx": missing_onnx,
                "max_box_error_px": box_max,
                "max_confidence_error": conf_max,
                "minimum_matched_iou": iou_min,
                "pass": frame_pass,
            })

            print(
                f"Frame {frame_index + 1:02d}/{FRAME_COUNT}: "
                f"PT={len(pt_detections)}, "
                f"ONNX={len(onnx_detections)}, "
                f"matched={len(matches)}, "
                f"unmatched={missing_pt + missing_onnx}, "
                f"box_error={box_max:.4f}px, "
                f"conf_error={conf_max:.6f}, "
                f"{'PASS' if frame_pass else 'FAIL'}"
            )

    finally:
        cap.release()

    csv_path = OUT / "50_frame_equivalence.csv"
    report_path = OUT / "50_frame_equivalence.md"

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    all_frames_pass = all(row["pass"] for row in rows)

    report = [
        "# PyTorch vs ONNX — 50-frame equivalence",
        "",
        f"Date: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Configuration",
        f"- Frames: {FRAME_COUNT} (first 50 sequential video frames)",
        f"- Input: {IMGSZ} x {IMGSZ}, FP32",
        f"- Confidence: {CONF}",
        f"- NMS IoU: {IOU}",
        f"- Class-agnostic NMS: False",
        f"- Maximum detections: {MAX_DET}",
        f"- Bounding-box tolerance: {BOX_TOLERANCE} pixels",
        f"- Confidence tolerance: {CONF_TOLERANCE}",
        "",
        "## Aggregate results",
        f"- PyTorch detections: {total_pt}",
        f"- ONNX detections: {total_onnx}",
        f"- Matched detections: {total_matched}",
        f"- Unmatched PyTorch detections: {total_unmatched_pt}",
        f"- Unmatched ONNX detections: {total_unmatched_onnx}",
        f"- Maximum matched box error: {max(all_box_errors, default=0):.6f} px",
        f"- Maximum matched confidence error: {max(all_conf_errors, default=0):.8f}",
        f"- Minimum matched IoU: {min(all_ious, default=1):.8f}",
        "",
        "## Frame results",
        "",
        "| Frame | PT | ONNX | Matched | Unmatched PT | Unmatched ONNX | Max box error (px) | Max confidence error | Result |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for r in rows:
        report.append(
            f"| {r['frame'] + 1} | {r['pytorch_detections']} "
            f"| {r['onnx_detections']} | {r['matched']} "
            f"| {r['unmatched_pytorch']} | {r['unmatched_onnx']} "
            f"| {r['max_box_error_px']:.4f} "
            f"| {r['max_confidence_error']:.6f} "
            f"| {'PASS' if r['pass'] else 'FAIL'} |"
        )

    report.extend([
        "",
        "## Final assessment",
        "",
        f"Overall result: {'PASS' if all_frames_pass else 'FAIL'}",
        "",
        "Matching uses greedy highest-IoU pairing within the same class. "
        "Unmatched detections are counted as mismatches. "
        "This is a numerical equivalence check, not an accuracy evaluation.",
    ])

    report_path.write_text("\n".join(report) + "\n")

    print("\n===== 50-FRAME SUMMARY =====")
    print("Frames tested:", len(rows))
    print("PyTorch detections:", total_pt)
    print("ONNX detections:", total_onnx)
    print("Matched detections:", total_matched)
    print("Unmatched PyTorch:", total_unmatched_pt)
    print("Unmatched ONNX:", total_unmatched_onnx)
    print("Maximum box error:", max(all_box_errors, default=0), "pixels")
    print("Maximum confidence error:", max(all_conf_errors, default=0))
    print("Overall:", "PASS" if all_frames_pass else "FAIL")
    print("CSV:", csv_path)
    print("Report:", report_path)


if __name__ == "__main__":
    main()
