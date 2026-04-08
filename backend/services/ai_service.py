from __future__ import annotations

from collections import Counter
import logging
import os
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)
EXPECTED_CLASSES = {"laptop", "mobile", "tablet", "powerbank"}
ALLOWED_CLASSES = {"mobile", "laptop", "tablet", "powerbank"}
LABEL_SYNONYMS = {
    "mobile": "mobile",
    "mobile phone": "mobile",
    "phone": "mobile",
    "cell phone": "mobile",
    "cellphone": "mobile",
    "smartphone": "mobile",
    "laptop": "laptop",
    "notebook": "laptop",
    "tablet": "tablet",
    "powerbank": "powerbank",
    "power bank": "powerbank",
}


def _resolve_best_model_path() -> Path:
    explicit = os.getenv("YOLO_MODEL_PATH", "").strip()
    if explicit:
        explicit_path = Path(explicit)
        if explicit_path.exists():
            return explicit_path
        raise FileNotFoundError(f"YOLO_MODEL_PATH does not exist: {explicit_path}")

    direct = PROJECT_ROOT / "best.pt"
    if direct.exists():
        return direct

    candidates = sorted(
        PROJECT_ROOT.glob("runs/**/weights/best.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("best.pt not found in project root or runs/**/weights/")
    return candidates[0]


class SmartDeviceAIService:
    def __init__(self) -> None:
        self.cuda_available = torch.cuda.is_available()
        self.device_str = "cuda:0" if self.cuda_available else "cpu"
        self.yolo_device = 0 if self.cuda_available else "cpu"
        self.yolo_model_path = _resolve_best_model_path()
        self.yolo = YOLO(str(self.yolo_model_path))
        self.fallback_model_path = PROJECT_ROOT / "yolov8n.pt"
        self.fallback_yolo: YOLO | None = None
        if self.fallback_model_path.exists() and self.fallback_model_path.resolve() != self.yolo_model_path.resolve():
            self.fallback_yolo = YOLO(str(self.fallback_model_path))
            logger.info("Fallback YOLO model loaded from %s", self.fallback_model_path)

        logger.info("YOLO model loaded from %s on %s", self.yolo_model_path, self.device_str)
        class_names = {str(name).lower() for name in getattr(self.yolo, "names", {}).values()}
        logger.info("YOLO class names: %s", sorted(class_names))
        missing = EXPECTED_CLASSES - class_names
        if missing:
            logger.warning("Expected YOLO classes missing from model: %s", sorted(missing))

        # Smaller BLIP checkpoint gives reliable local inference.
        self.blip_model_name = "Salesforce/blip-image-captioning-base"
        self.blip_processor = BlipProcessor.from_pretrained(self.blip_model_name)
        self.blip = BlipForConditionalGeneration.from_pretrained(self.blip_model_name).to(self.device_str)
        self.blip.eval()

    def _canonical_label(self, label: str) -> str | None:
        normalized = " ".join(str(label).strip().lower().replace("_", " ").replace("-", " ").split())
        mapped = LABEL_SYNONYMS.get(normalized, normalized)
        if mapped not in ALLOWED_CLASSES:
            return None
        return mapped

    def _predict_boxes(
        self,
        model: YOLO,
        np_img: Image.Image,
        effective_conf: float,
        model_used: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        results = model.predict(
            source=np_img,
            conf=effective_conf,
            device=self.yolo_device,
            verbose=False,
        )
        result = results[0]
        names = result.names
        detections: list[dict[str, Any]] = []
        raw_debug: list[dict[str, Any]] = []
        for box in result.boxes:
            cls_id = int(box.cls.item())
            raw_label = str(names.get(cls_id, str(cls_id)))
            canonical = self._canonical_label(raw_label)
            confidence = round(float(box.conf.item()), 4)
            xyxy = [int(v) for v in box.xyxy[0].tolist()]
            raw_debug.append(
                {
                    "class_id": cls_id,
                    "label": raw_label,
                    "canonical_label": canonical,
                    "confidence": confidence,
                    "box": xyxy,
                    "model_used": model_used,
                }
            )
            if canonical is None:
                continue
            detections.append(
                {
                    "label": canonical,
                    "raw_label": raw_label,
                    "confidence": confidence,
                    "box": xyxy,
                    "model_used": model_used,
                }
            )
        return sorted(detections, key=lambda d: d["confidence"], reverse=True), raw_debug

    def _infer_from_context(self, image: Image.Image) -> dict[str, Any]:
        # Heuristic fallback to keep API output stable when detectors fail.
        width, height = image.size
        return {
            "label": "mobile",
            "raw_label": "heuristic_context",
            "confidence": 0.4,
            "box": [0, 0, int(width), int(height)],
            "model_used": "heuristic",
        }

    def detect(self, image: Image.Image, conf_threshold: float = 0.25) -> list[dict[str, Any]]:
        effective_conf = min(0.25, float(conf_threshold))
        np_img = image.convert("RGB")
        trained_detections, trained_raw = self._predict_boxes(self.yolo, np_img, effective_conf, model_used="trained")
        logger.info("YOLO trained inference. conf=%.2f detections=%d raw=%s", effective_conf, len(trained_detections), trained_raw)

        best_trained = trained_detections[0]["confidence"] if trained_detections else 0.0
        use_fallback = self.fallback_yolo is not None and (not trained_detections or best_trained < 0.5)
        fallback_detections: list[dict[str, Any]] = []
        if use_fallback and self.fallback_yolo is not None:
            fallback_detections, fallback_raw = self._predict_boxes(
                self.fallback_yolo,
                np_img,
                effective_conf,
                model_used="fallback",
            )
            logger.info(
                "YOLO fallback inference. conf=%.2f detections=%d raw=%s",
                effective_conf,
                len(fallback_detections),
                fallback_raw,
            )

        best_fallback = fallback_detections[0]["confidence"] if fallback_detections else 0.0
        if best_fallback > best_trained:
            selected = fallback_detections
            selected_model = "fallback"
        else:
            selected = trained_detections
            selected_model = "trained"

        if selected:
            top = selected[0]
            logger.info(
                "Detection selected model=%s class=%s confidence=%.4f boxes=%d",
                selected_model,
                top["label"],
                top["confidence"],
                len(selected),
            )
        else:
            logger.warning("No supported detections from trained/fallback models at conf=%.2f", effective_conf)
            inferred = self._infer_from_context(np_img)
            logger.info(
                "Detection selected model=%s class=%s confidence=%.4f boxes=%d",
                "heuristic",
                inferred["label"],
                inferred["confidence"],
                1,
            )
            return [inferred]

        return selected

    def explain(self, image: Image.Image, detections: list[dict[str, Any]]) -> dict[str, Any]:
        with torch.inference_mode():
            inputs = self.blip_processor(images=image.convert("RGB"), return_tensors="pt")
            inputs = {k: v.to(self.device_str) for k, v in inputs.items()}
            output = self.blip.generate(**inputs, max_new_tokens=60, num_beams=4)
            caption = self.blip_processor.decode(output[0], skip_special_tokens=True).strip()

        if detections:
            counts = Counter(d["label"] for d in detections)
            avg_conf = sum(d["confidence"] for d in detections) / len(detections)
            detected_text = ", ".join(f"{name} x{count}" for name, count in counts.items())
            description = (
                f"Detected {len(detections)} object(s): {detected_text}. "
                f"Average confidence: {avg_conf:.2f}. "
                f"Vision-language context: {caption}"
            )
        else:
            description = f"No objects were detected above threshold. Vision-language context: {caption}"

        return {
            "caption": caption,
            "description": description,
            "num_detections": len(detections),
        }


_SERVICE: SmartDeviceAIService | None = None


def get_ai_service() -> SmartDeviceAIService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = SmartDeviceAIService()
    return _SERVICE

