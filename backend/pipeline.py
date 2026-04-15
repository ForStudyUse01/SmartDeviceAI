"""
E-waste Detection Pipeline
Orchestrates YOLO detection + fallback device detection + condition analysis.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from device_detector import SmartDeviceDetector
from vlm_model import VLMAnalyzer
from yolo_model import BoundingBox, YoloDetector
from recommendation_engine import RecommendationEngine

logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    yolo_label: str
    yolo_confidence: float
    vlm_object: str
    condition: str
    details: str
    suggestion: str
    eco_score: int
    box: tuple[int, int, int, int]
    vlm_condition: str = "Average"
    vlm_damage: str = "Not Broken"
    damage_confidence: float = 0.5


@dataclass
class PipelineResult:
    status: str
    image_name: str
    detected_objects: list[DetectedObject]
    error_message: Optional[str] = None
    num_detections: int = 0

    def __post_init__(self) -> None:
        self.num_detections = len(self.detected_objects)


@dataclass
class BatchResult:
    status: str
    total_images: int
    successful: int
    failed: int
    results: list[PipelineResult]
    total_objects_detected: int = 0

    def __post_init__(self) -> None:
        self.total_objects_detected = sum(result.num_detections for result in self.results)


class E_WasteDetectionPipeline:
    def __init__(
        self,
        yolo_model_path: str = "yolov8n.pt",
        vlm_model_name: str = "Salesforce/blip2-opt-2.7b",
    ) -> None:
        logger.info("Initializing E-waste Detection Pipeline")
        self.yolo_detector = YoloDetector(yolo_model_path)
        self.vlm_analyzer = VLMAnalyzer(vlm_model_name)
        self.device_detector = SmartDeviceDetector()
        self.recommendation_engine = RecommendationEngine()
        logger.info("Pipeline initialized successfully")

    def _build_fallback_box(self, image: Image.Image, image_bytes: bytes, image_name: str) -> list[BoundingBox]:
        quick_detection = self.yolo_detector.detect_single(image_bytes, image_name)

        if quick_detection.detected_device != "unknown":
            logger.info(
                "Using quick detector fallback for %s: %s (%.2f)",
                image_name,
                quick_detection.detected_device,
                quick_detection.confidence,
            )
            return [
                BoundingBox(
                    x1=0,
                    y1=0,
                    x2=image.width,
                    y2=image.height,
                    label=quick_detection.detected_device,
                    confidence=quick_detection.confidence,
                )
            ]

        device_type, device_confidence = self.device_detector.detect_device_from_image(image_bytes)
        if device_confidence > 0.30:
            logger.info(
                "Using smart detector fallback for %s: %s (%.2f)",
                image_name,
                device_type,
                device_confidence,
            )
            return [
                BoundingBox(
                    x1=0,
                    y1=0,
                    x2=image.width,
                    y2=image.height,
                    label=device_type,
                    confidence=round(device_confidence * 100, 2),
                )
            ]

        return []

    def _filter_condition(self, analysis, yolo_confidence: float) -> tuple[str, float]:
        if yolo_confidence < 40:
            return "ignore", 0.0

        indicators = getattr(analysis, "damage_indicators", [])
        if analysis.damage == "Broken":
            return "damaged", max(analysis.damage_confidence, analysis.confidence, 0.7)
        if analysis.condition == "damaged":
            return "damaged", max(analysis.confidence, 0.62)
        if len(indicators) >= 2:
            return "damaged", max(analysis.confidence, 0.7)

        return "working", max(analysis.confidence, 0.6)

    def _merge_with_full_image_damage(self, local_analysis, full_image_analysis):
        """Apply whole-image damage cues to per-box analysis for crack misses."""
        if full_image_analysis.damage != "Broken":
            return local_analysis
        if local_analysis.damage == "Broken":
            return local_analysis
        if full_image_analysis.damage_confidence < 0.6:
            return local_analysis

        merged_indicators = list(local_analysis.damage_indicators)
        for indicator in full_image_analysis.damage_indicators:
            if indicator not in merged_indicators:
                merged_indicators.append(indicator)

        local_analysis.damage = "Broken"
        local_analysis.damage_confidence = max(local_analysis.damage_confidence, full_image_analysis.damage_confidence)
        local_analysis.condition = "damaged"
        local_analysis.condition_label = "Bad"
        local_analysis.damage_indicators = merged_indicators
        local_analysis.suggestion = (
            f"{local_analysis.suggestion} Whole-image pass detected strong damage cues."
        ).strip()
        return local_analysis

    def _finalize_damage_state(self, analysis, filtered_condition: str):
        """
        Keep damage label/confidence aligned with strong damage signals.
        """
        strong_damage = (
            filtered_condition == "damaged"
            or analysis.condition == "damaged"
            or analysis.condition_label == "Bad"
            or analysis.damage == "Broken"
            or len(getattr(analysis, "damage_indicators", [])) >= 2
        )
        if strong_damage:
            analysis.damage = "Broken"
            analysis.condition = "damaged"
            analysis.condition_label = "Bad"
            analysis.damage_confidence = max(float(getattr(analysis, "damage_confidence", 0.0)), 0.72)
        return analysis

    def process_single_image(
        self,
        image_bytes: bytes,
        image_name: str = "image.jpg",
        conf_threshold: float = 0.25,
    ) -> PipelineResult:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            full_image_analysis = self.vlm_analyzer.analyze_crop(image_bytes, "image/jpeg")
            boxes = self.yolo_detector.detect_objects(image_bytes, conf_threshold=conf_threshold)

            if not boxes:
                boxes = self._build_fallback_box(image, image_bytes, image_name)

            if not boxes:
                logger.info("No objects detected in %s", image_name)
                return PipelineResult(status="success", image_name=image_name, detected_objects=[])

            detected_objects: list[DetectedObject] = []

            for idx, box in enumerate(boxes):
                try:
                    x1 = max(0, box.x1)
                    y1 = max(0, box.y1)
                    x2 = min(image.width, box.x2)
                    y2 = min(image.height, box.y2)

                    if x2 <= x1 or y2 <= y1:
                        logger.warning("Invalid box dimensions for object %s", idx)
                        continue

                    crop = image.crop((x1, y1, x2, y2))
                    crop_io = io.BytesIO()
                    crop.save(crop_io, format="JPEG", quality=85)
                    crop_bytes = crop_io.getvalue()

                    analysis = self.vlm_analyzer.analyze_crop(crop_bytes, "image/jpeg")
                    analysis = self._merge_with_full_image_damage(analysis, full_image_analysis)
                    filtered_condition, filtered_confidence = self._filter_condition(
                        analysis,
                        box.confidence,
                    )
                    analysis = self._finalize_damage_state(analysis, filtered_condition)

                    if filtered_condition == "ignore":
                        continue

                    # Recommendation Engine logic
                    rec_result = self.recommendation_engine.evaluate(
                        device_type=analysis.object_name,
                        eco_score=analysis.eco_score,
                        damage_indicators=analysis.damage_indicators,
                        raw_working_status=filtered_condition
                    )
                    
                    combined_condition = f"{rec_result.condition_category} & {rec_result.working_status}"

                    detected_objects.append(
                        DetectedObject(
                            yolo_label=box.label,
                            yolo_confidence=round(filtered_confidence * 100, 2),
                            vlm_object=analysis.object_name,
                            condition=combined_condition,
                            vlm_condition=analysis.condition_label,
                            vlm_damage=analysis.damage,
                            damage_confidence=round(float(analysis.damage_confidence), 4),
                            details=rec_result.details,
                            suggestion=rec_result.recommendation,
                            eco_score=analysis.eco_score,
                            box=(x1, y1, x2, y2),
                        )
                    )
                except Exception as exc:
                    logger.error("Error processing box %s: %s", idx, exc)

            return PipelineResult(status="success", image_name=image_name, detected_objects=detected_objects)
        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", image_name, exc)
            return PipelineResult(
                status="error",
                image_name=image_name,
                detected_objects=[],
                error_message=str(exc),
            )

    def process_batch(
        self,
        image_list: list[tuple[bytes, str]],
        conf_threshold: float = 0.25,
    ) -> BatchResult:
        logger.info("Processing batch of %s images", len(image_list))

        results: list[PipelineResult] = []
        successful = 0
        failed = 0

        for image_bytes, image_name in image_list:
            result = self.process_single_image(
                image_bytes,
                image_name=image_name,
                conf_threshold=conf_threshold,
            )
            results.append(result)

            if result.status == "success":
                successful += 1
            else:
                failed += 1

        return BatchResult(
            status="success" if failed == 0 else "partial",
            total_images=len(image_list),
            successful=successful,
            failed=failed,
            results=results,
        )


_pipeline_instance: Optional[E_WasteDetectionPipeline] = None


def get_pipeline() -> E_WasteDetectionPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = E_WasteDetectionPipeline()
    return _pipeline_instance
