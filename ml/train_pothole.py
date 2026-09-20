from pathlib import Path
from ultralytics import YOLO
import torch

DATA = "ml/data.yaml"
MODEL = "yolov8n.pt"

device = "mps" if torch.backends.mps.is_available() else "cpu"

print(f"Training device: {device}")

model = YOLO(MODEL)

results = model.train(
    data=DATA,
    epochs=40,
    imgsz=416,
    batch=8,
    patience=8,
    device=device,
    project="runs",
    name="pothole_v1",
    pretrained=True,
    workers=4,
    verbose=True,
)

print("\nTraining complete.")
print("Best model:", Path("runs/pothole_v1/weights/best.pt").resolve())
print("Last model:", Path("runs/pothole_v1/weights/last.pt").resolve())
