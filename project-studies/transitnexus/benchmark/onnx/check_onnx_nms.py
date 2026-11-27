import cv2
import numpy as np
import torch
import onnxruntime as ort

from pathlib import Path
from ultralytics import YOLO
from ultralytics.data.augment import LetterBox
from ultralytics.utils import nms


ROOT = Path.home() / "transitnexus-sih"
MODEL_PATH = ROOT / "models/pothole/best.pt"
ONNX_PATH = ROOT / "models/pothole/best_benchmark.onnx"
VIDEO_PATH = ROOT / "data/benchmark/bench_clip_fixed.mp4"

IMGSZ = 640
CONF = 0.25
IOU = 0.70


def preprocess(frame):
    letterbox = LetterBox(
        new_shape=(IMGSZ, IMGSZ),
        auto=False,
        scale_fill=False,
        scaleup=True,
        center=True,
        stride=32,
        padding_value=114,
        interpolation=cv2.INTER_LINEAR,
    )

    image = letterbox(image=frame)
    image = image[:, :, ::-1].transpose(2, 0, 1)
    image = np.ascontiguousarray(image[None], dtype=np.float32)
    return image / 255.0


def extract_prediction(output):
    if isinstance(output, (tuple, list)):
        output = output[0]
    if not isinstance(output, torch.Tensor):
        raise TypeError(f"Unexpected PyTorch output: {type(output)}")
    return output


def apply_nms(prediction):
    return nms.non_max_suppression(
        prediction.clone(),
        conf_thres=CONF,
        iou_thres=IOU,
        classes=None,
        agnostic=False,
        multi_label=False,
        max_det=300,
        nc=1,
        end2end=False,
    )


def main():
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    ok, frame = cap.read()
    cap.release()

    if not ok:
        raise RuntimeError("Could not read benchmark frame")

    model = YOLO(str(MODEL_PATH))
    model.predict(
        source=frame,
        imgsz=IMGSZ,
        conf=CONF,
        iou=IOU,
        rect=False,
        device="cpu",
        verbose=False,
    )

    tensor = torch.from_numpy(preprocess(frame))

    session = ort.InferenceSession(
        str(ONNX_PATH),
        providers=["CPUExecutionProvider"],
    )

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    with torch.inference_mode():
        pt_output = extract_prediction(model.model(tensor))

    ort_output = session.run(
        [output_name],
        {input_name: tensor.numpy()},
    )[0]

    pt_detections = apply_nms(pt_output)
    ort_tensor = torch.from_numpy(ort_output)
    ort_detections = apply_nms(ort_tensor)

    print("\n===== RAW MODEL OUTPUTS =====")
    print("PyTorch shape:", tuple(pt_output.shape))
    print("ONNX shape:", tuple(ort_tensor.shape))
    print("PyTorch dtype:", pt_output.dtype)
    print("ONNX dtype:", ort_tensor.dtype)
    print("Raw maximum absolute difference:",
          float((pt_output.cpu() - ort_tensor).abs().max()))

    print("\n===== SHARED NMS RESULTS =====")
    print("PyTorch detections:", len(pt_detections[0]))
    print("ONNX detections:", len(ort_detections[0]))

    print("\n===== NMS SETTINGS =====")
    print("Confidence:", CONF)
    print("IoU:", IOU)
    print("Class-agnostic:", False)
    print("Multi-label:", False)
    print("Maximum detections:", 300)
    print("Classes:", 1)

    print("\n===== RESULT =====")
    if pt_output.shape != ort_tensor.shape:
        raise RuntimeError("Raw output shapes do not match")

    print("PASS: Both models produced compatible raw output shapes.")
    print("PASS: Shared Ultralytics NMS executed on both outputs.")
    print("Note: Detection equivalence still requires the 50-frame test.")


if __name__ == "__main__":
    main()
