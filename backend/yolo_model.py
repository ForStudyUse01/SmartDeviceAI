from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Optional

from PIL import Image

from utils import normalize_device_label

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

logger = logging.getLogger(__name__)

# Mapping from COCO/pretrained labels to e-waste categories
YOLO_TO_DEVICE = {
    "cell phone": "phone",
    "laptop": "laptop",
    "tv": "electronic device",
    "mouse": "e-waste component",
    "keyboard": "keyboard",
    "remote": "remote",
    "charger": "charger",
    "battery": "battery",
    "monitor": "electronic device",
    "computer": "laptop",
    "mobile": "phone",
}

SUPPORTED_DEVICE_LABELS = {
    "phone", "laptop", "tablet", "charger", "powerbank", "pcb",
    "battery", "wire", "electronic device", "e-waste component",
    "keyboard", "remote", "unknown"
}


@dataclass
class DetectionResult:
    detected_device: str
    confidence: float
    raw_labels: list[str]


@dataclass
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int
    label: str
    confidence: float


@dataclass
class TrainingConfig:
    """Configuration for YOLO fine-tuning"""
    data_yaml: str  # Path to data.yaml
    epochs: int = 50
    imgsz: int = 640
    batch_size: int = 8
    device: int = 0  # GPU device ID, or -1 for CPU
    patience: int = 20  # Early stopping patience
    name: str = "e-waste-detector"  # Training run name


class YoloDetector:
    """YOLO v8 detector for e-waste objects with fine-tuning support"""

    def __init__(self, model_path: str = "yolov8n.pt") -> None:
        """
        Initialize YOLO detector.

        Args:
            model_path: Path to YOLO weights (.pt file)
        """
        self.model = None
        self.model_path = model_path
        self._load_model()

    def _load_model(self) -> None:
        """Load pretrained YOLO model"""
        if YOLO is None:
            logger.warning("ultralytics not available - detection disabled")
            return

        try:
            logger.info(f"Loading YOLO model: {self.model_path}")
            self.model = YOLO(self.model_path)
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None

    def fine_tune(
        self,
        config: TrainingConfig,
        on_progress_callback=None,
    ) -> dict:
        """
        Fine-tune YOLO on custom e-waste dataset.

        Args:
            config: TrainingConfig with paths and hyperparameters
            on_progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with training results and paths
        """
        if self.model is None:
            raise RuntimeError("YOLO model not loaded")

        if not Path(config.data_yaml).exists():
            raise FileNotFoundError(f"data.yaml not found at {config.data_yaml}")

        try:
            logger.info(f"Starting YOLO fine-tuning with config: {config}")

            # Train the model
            results = self.model.train(
                data=config.data_yaml,
                epochs=config.epochs,
                imgsz=config.imgsz,
                batch=config.batch_size,
                device=config.device,
                patience=config.patience,
                name=config.name,
                save=True,
                exist_ok=True,
                verbose=True,
            )

            # Get best model path
            best_model_path = Path(results.save_dir) / "weights" / "best.pt"

            logger.info(f"Fine-tuning completed. Best model: {best_model_path}")

            # Load the best model
            if best_model_path.exists():
                self.model = YOLO(str(best_model_path))
                self.model_path = str(best_model_path)

            return {
                "status": "success",
                "best_model_path": str(best_model_path),
                "metrics": {
                    "final_epoch": config.epochs,
                    "best_epoch": results.best_epoch if hasattr(results, "best_epoch") else None,
                },
            }

        except Exception as e:
            logger.error(f"Fine-tuning failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
            }

    def validate(self, data_yaml: str) -> dict:
        """
        Validate YOLO model on dataset.

        Args:
            data_yaml: Path to data.yaml

        Returns:
            Validation metrics
        """
        if self.model is None:
            raise RuntimeError("YOLO model not loaded")

        try:
            results = self.model.val(data=data_yaml, verbose=False)
            return {
                "status": "success",
                "metrics": {
                    "map50": results.box.map50,
                    "map": results.box.map,
                },
            }
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"status": "failed", "error": str(e)}

    def load_model(self, model_path: str) -> None:
        """Load a different YOLO model"""
        if YOLO is None:
            logger.warning("ultralytics not available")
            return

        try:
            self.model = YOLO(model_path)
            self.model_path = model_path
            logger.info(f"Model loaded: {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model {model_path}: {e}")

    def _fallback_from_filename(self, filename: str) -> str:
        """Try to guess device type from filename"""
        lowered = filename.lower()
        for keyword in ("phone", "laptop", "tablet", "charger", "powerbank", "pcb", "battery", "wire"):
            if keyword in lowered:
                return keyword
        return "unknown"

    def detect_single(self, image_bytes: bytes, filename: str = "upload.jpg") -> DetectionResult:
        """
        Detect objects in a single image.

        Args:
            image_bytes: Image data
            filename: Original filename (for fallback detection)

        Returns:
            DetectionResult with device type and confidence
        """
        if self.model is None:
            fallback = self._fallback_from_filename(filename)
            return DetectionResult(detected_device=fallback, confidence=35.0, raw_labels=[fallback])

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            results = self.model.predict(image, verbose=False, conf=0.25)

            labels: list[str] = []
            confidences: list[float] = []

            for result in results:
                names = result.names
                for box in getattr(result, "boxes", []):
                    class_id = int(box.cls.item())
                    label = YOLO_TO_DEVICE.get(names[class_id], names[class_id])
                    normalized = normalize_device_label(label)

                    if normalized in SUPPORTED_DEVICE_LABELS:
                        labels.append(normalized)
                        confidences.append(float(box.conf.item()) * 100)

            if not labels:
                fallback = self._fallback_from_filename(filename)
                return DetectionResult(detected_device=fallback, confidence=25.0, raw_labels=[fallback])

            detected = Counter(labels).most_common(1)[0][0]
            avg_conf = round(sum(confidences) / len(confidences), 2)

            return DetectionResult(detected_device=detected, confidence=avg_conf, raw_labels=labels)

        except Exception as e:
            logger.error(f"Detection failed: {e}")
            fallback = self._fallback_from_filename(filename)
            return DetectionResult(detected_device=fallback, confidence=15.0, raw_labels=[fallback])

    def detect_many(self, items: Iterable[tuple[bytes, str]]) -> DetectionResult:
        """
        Detect objects in multiple images and aggregate results.

        Args:
            items: Iterable of (image_bytes, filename) tuples

        Returns:
            Aggregated DetectionResult
        """
        detections = [self.detect_single(content, name) for content, name in items]
        labels = [item.detected_device for item in detections if item.detected_device != "unknown"]

        if not labels:
            labels = [item.detected_device for item in detections]

        detected = Counter(labels).most_common(1)[0][0] if labels else "unknown"
        confidence = round(sum(item.confidence for item in detections) / max(len(detections), 1), 2)

        return DetectionResult(detected_device=detected, confidence=confidence, raw_labels=labels)

    def detect_objects(self, image_bytes: bytes, conf_threshold: float = 0.25) -> List[BoundingBox]:
        """
        Run inference and return bounding boxes for all detected objects.

        Args:
            image_bytes: Image data
            conf_threshold: Confidence threshold (0-1)

        Returns:
            List of BoundingBox objects
        """
        if self.model is None:
            logger.warning("YOLO model not available")
            return []

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            results = self.model.predict(image, verbose=False, conf=conf_threshold)

            boxes_out = []

            for result in results:
                names = result.names
                for box in getattr(result, "boxes", []):
                    class_id = int(box.cls.item())
                    label = YOLO_TO_DEVICE.get(names[class_id], names[class_id])
                    normalized = normalize_device_label(label)

                    if normalized in SUPPORTED_DEVICE_LABELS:
                        xyxy = box.xyxy[0].tolist()
                        conf = float(box.conf.item()) * 100

                        boxes_out.append(BoundingBox(
                            x1=int(xyxy[0]),
                            y1=int(xyxy[1]),
                            x2=int(xyxy[2]),
                            y2=int(xyxy[3]),
                            label=normalized,
                            confidence=round(conf, 2)
                        ))

            return boxes_out

        except Exception as e:
            logger.error(f"detect_objects failed: {e}")
            return []

