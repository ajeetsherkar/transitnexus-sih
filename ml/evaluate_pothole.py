from pathlib import Path

from ultralytics import YOLO


MODEL = Path("runs/detect/runs/pothole_v1/weights/best.pt")
DATA = "ml/data.yaml"


def evaluate(split: str):
    print(f"\n=== Evaluating {split.upper()} split ===")

    model = YOLO(str(MODEL))

    results = model.val(
        data=DATA,
        split=split,
        imgsz=416,
        device="mps",
        project="runs",
        name=f"pothole_v1_{split}",
        plots=True,
        verbose=True,
    )

    metrics = results.results_dict

    print(f"\n{split.upper()} RESULTS")
    print(f"Precision:  {metrics.get('metrics/precision(B)', 'N/A')}")
    print(f"Recall:     {metrics.get('metrics/recall(B)', 'N/A')}")
    print(f"mAP50:      {metrics.get('metrics/mAP50(B)', 'N/A')}")
    print(f"mAP50-95:   {metrics.get('metrics/mAP50-95(B)', 'N/A')}")

    if hasattr(results, "speed"):
        print(f"Speed:      {results.speed}")

    return results


if __name__ == "__main__":
    if not MODEL.exists():
        raise FileNotFoundError(f"Model not found: {MODEL.resolve()}")

    print(f"Model: {MODEL.resolve()}")
    print(f"Dataset config: {Path(DATA).resolve()}")

    evaluate("val")
    evaluate("test")

    print("\nEvaluation complete.")
