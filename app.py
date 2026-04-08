from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st
import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor
from ultralytics import YOLO


st.set_page_config(page_title="SmartDeviceAI (YOLO + VLM)", layout="wide")
st.title("SmartDeviceAI: YOLOv8 + Vision Language Model")


def resolve_best_model() -> Path:
    root = Path(__file__).resolve().parent
    direct = root / "best.pt"
    if direct.exists():
        return direct

    candidates = sorted(
        root.glob("runs/**/weights/best.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("Could not find best.pt in project root or runs/**/weights/")
    return candidates[0]


@st.cache_resource(show_spinner=False)
def load_yolo_model() -> tuple[YOLO, int, Path]:
    model_path = resolve_best_model()
    model = YOLO(str(model_path))
    device = 0 if torch.cuda.is_available() else -1
    return model, device, model_path


@st.cache_resource(show_spinner=False)
def load_blip_model() -> tuple[BlipProcessor, BlipForConditionalGeneration, str]:
    model_id = "Salesforce/blip-image-captioning-base"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = BlipProcessor.from_pretrained(model_id)
    model = BlipForConditionalGeneration.from_pretrained(model_id).to(device)
    model.eval()
    return processor, model, device


def run_detection(model: YOLO, device: int, image: Image.Image, conf: float = 0.25) -> tuple[Any, list[dict[str, Any]], np.ndarray]:
    image_np = np.array(image.convert("RGB"))
    results = model.predict(source=image_np, conf=conf, device=device, verbose=False)
    result = results[0]

    detections: list[dict[str, Any]] = []
    names = result.names
    for box in result.boxes:
        cls_id = int(box.cls.item())
        label = names.get(cls_id, str(cls_id))
        confidence = float(box.conf.item())
        xyxy = [int(v) for v in box.xyxy[0].tolist()]
        detections.append({"label": label, "confidence": confidence, "box": xyxy})

    plotted = result.plot()
    plotted_rgb = cv2.cvtColor(plotted, cv2.COLOR_BGR2RGB)
    return result, detections, plotted_rgb


def generate_vlm_caption(processor: BlipProcessor, model: BlipForConditionalGeneration, device: str, image: Image.Image) -> str:
    with torch.inference_mode():
        inputs = processor(images=image.convert("RGB"), return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        output = model.generate(**inputs, max_new_tokens=60, num_beams=4)
    return processor.decode(output[0], skip_special_tokens=True).strip()


def build_explanation(detections: list[dict[str, Any]], caption: str) -> str:
    if not detections:
        return f"No target devices were confidently detected. VLM sees: {caption}"

    counts = Counter(d["label"] for d in detections)
    count_text = ", ".join(f"{name} x{count}" for name, count in counts.items())
    avg_conf = sum(d["confidence"] for d in detections) / len(detections)
    return (
        f"Detected {len(detections)} object(s): {count_text}. "
        f"Average confidence: {avg_conf:.2f}. "
        f"VLM context: {caption}"
    )


with st.sidebar:
    st.subheader("Runtime")
    use_gpu = torch.cuda.is_available()
    st.write(f"CUDA available: **{use_gpu}**")
    if use_gpu:
        st.write(f"GPU: **{torch.cuda.get_device_name(0)}**")
    st.caption("Upload an image to run YOLO detection and BLIP explanation.")


uploaded_file = st.file_uploader("Upload image", type=["jpg", "jpeg", "png", "webp", "bmp"])
conf_threshold = st.slider("Detection confidence threshold", min_value=0.05, max_value=0.90, value=0.25, step=0.05)

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Input Image", use_column_width=True)

    with st.spinner("Loading models..."):
        yolo_model, yolo_device, yolo_path = load_yolo_model()
        blip_processor, blip_model, blip_device = load_blip_model()

    st.info(f"YOLO model: `{yolo_path}` | YOLO device: `{'cuda:0' if yolo_device == 0 else 'cpu'}` | BLIP device: `{blip_device}`")

    with st.spinner("Running YOLO + VLM..."):
        _, detections, boxed_image = run_detection(yolo_model, yolo_device, image, conf=conf_threshold)
        caption = generate_vlm_caption(blip_processor, blip_model, blip_device, image)
        explanation = build_explanation(detections, caption)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.image(boxed_image, caption="Detections with Bounding Boxes", use_column_width=True)
    with col2:
        st.subheader("Detected Objects")
        if detections:
            for idx, det in enumerate(detections, 1):
                st.write(f"{idx}. **{det['label']}** (conf: {det['confidence']:.2f})")
        else:
            st.write("No objects detected above threshold.")

        st.subheader("AI-Generated Description")
        st.write(explanation)

