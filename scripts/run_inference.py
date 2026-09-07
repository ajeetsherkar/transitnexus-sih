from pathlib import Path
import argparse

from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent.parent

VEHICLE_MODEL = BASE_DIR / "yolov8n.pt"
POTHOLE_MODEL = BASE_DIR / "models" / "pothole_best.pt"

OUTPUT_DIR = BASE_DIR / "runs" / "inference"


def run_inference(source: str, model_type: str, confidence: float):
    source_path = Path(source)

    if not source_path.exists():
        raise FileNotFoundError(f"Source not found: {source_path}")

    if model_type == "vehicle":
        model_path = VEHICLE_MODEL
    elif model_type == "pothole":
        model_path = POTHOLE_MODEL
    else:
        raise ValueError("model must be either 'vehicle' or 'pothole'")

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    print("=" * 60)
    print("TRANSITNEXUS INFERENCE")
    print("=" * 60)
    print(f"Model type : {model_type}")
    print(f"Model      : {model_path}")
    print(f"Source     : {source_path}")
    print(f"Confidence : {confidence}")
    print("=" * 60)

    model = YOLO(str(model_path))

    results = model.predict(
        source=str(source_path),
        conf=confidence,
        save=True,
        project=str(OUTPUT_DIR),
        name=model_type,
        exist_ok=True,
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("INFERENCE SUMMARY")
    print("=" * 60)
    print(f"Processed results: {len(results)}")

    total_detections = 0

    for index, result in enumerate(results, start=1):
        detections = len(result.boxes)
        total_detections += detections

        print(f"Result {index}: {detections} detections")

        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence_score = float(box.conf[0])
            class_name = result.names[class_id]

            print(
                f"  - {class_name}: "
                f"confidence={confidence_score:.3f}"
            )

    print(f"\nTotal detections: {total_detections}")
    print(f"Output directory: {OUTPUT_DIR / model_type}")
    print("✅ Inference completed successfully")


def main():
    parser = argparse.ArgumentParser(
        description="TransitNexus pretrained-model inference pipeline"
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Path to an image or video",
    )

    parser.add_argument(
        "--model",
        required=True,
        choices=["vehicle", "pothole"],
        help="Inference model to use",
    )

    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold (default: 0.25)",
    )

    args = parser.parse_args()

    run_inference(
        source=args.source,
        model_type=args.model,
        confidence=args.conf,
    )


if __name__ == "__main__":
    main()
