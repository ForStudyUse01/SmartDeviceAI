"""
Vision Language Model (VLM) Analyzer using BLIP-2
- Lightweight pretrained model from HuggingFace
- No external API required
- CPU-friendly inference
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
from PIL import Image, ImageStat
from transformers import Blip2Processor, Blip2ForConditionalGeneration

logger = logging.getLogger(__name__)

# Strict prompt for structured condition + damage outputs.
E_WASTE_PROMPT = """Analyze the uploaded device image.
Classify:
1. Overall condition: Good, Average, or Bad
2. Is the device broken? Answer: Broken or Not Broken

Rules:
- Good = no visible damage, clean
- Average = minor scratches or wear
- Bad = heavy damage, cracks, missing parts
- Broken = visible cracks, shattered screen, major defects

Return ONLY JSON:
{
  "condition": "...",
  "damage": "..."
}
"""


@dataclass
class VLMResult:
    """VLM analysis result"""
    object_name: str
    condition: str
    condition_label: str
    damage: str
    confidence: float
    suggestion: str
    eco_score: int
    damage_indicators: list[str]


class VLMAnalyzer:
    """Local BLIP-2 Vision Language Model Analyzer"""

    def __init__(self, model_name: str = "Salesforce/blip2-opt-2.7b"):
        """
        Initialize BLIP-2 model for e-waste analysis.

        Args:
            model_name: HuggingFace model identifier
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = os.getenv("VLM_FINETUNED_PATH", model_name)
        self.processor = None
        self.model = None
        # Prefer heavy VLM by default for accuracy; allow opt-out only when needed.
        self.enable_model = os.getenv("ENABLE_HEAVY_VLM", "1").lower() in {"1", "true", "yes", "on"}

        if self.enable_model:
            self._load_model()
        else:
            logger.info(
                "Heavy VLM disabled; using fast fallback analyzer. "
                "Set ENABLE_HEAVY_VLM=1 to enable BLIP-2."
            )

    def _load_model(self) -> None:
        """Load BLIP-2 model and processor"""
        try:
            logger.info(f"Loading BLIP-2 model: {self.model_name} on {self.device}")
            self.processor = Blip2Processor.from_pretrained(self.model_name)
            self.model = Blip2ForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                low_cpu_mem_usage=True,
            )
            self.model.to(self.device)
            if self.device == "cpu":
                self.model.half()  # Use float16 for smaller memory footprint
            logger.info("BLIP-2 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load BLIP-2 model: {e}")
            self.model = None
            self.processor = None

    def analyze_crop(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> VLMResult:
        """
        Analyze a single cropped image (from YOLO detection).

        Args:
            image_bytes: Image data as bytes
            mime_type: MIME type of the image

        Returns:
            VLMResult with object name, condition, suggestion, and eco_score
        """
        if self.model is None or self.processor is None:
            return self._fallback_analysis(image_bytes)

        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Prepare inputs
            inputs = self.processor(image, E_WASTE_PROMPT, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate response
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=100,
                    num_beams=1,
                    temperature=0.7,
                )

            response_text = self.processor.decode(
                output_ids[0], skip_special_tokens=True
            ).strip()

            # Parse JSON response
            return self._parse_response(response_text)

        except Exception as e:
            logger.warning(f"VLM analysis failed: {e}. Using fallback.")
            return self._fallback_analysis(image_bytes)

    def analyze_batch(self, image_list: list[bytes]) -> list[VLMResult]:
        """
        Analyze multiple images.

        Args:
            image_list: List of image bytes

        Returns:
            List of VLMResult objects
        """
        results = []
        for idx, image_bytes in enumerate(image_list):
            try:
                result = self.analyze_crop(image_bytes)
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing image {idx}: {e}")
                results.append(self._fallback_analysis(image_bytes))
        return results

    def _parse_response(self, response_text: str) -> VLMResult:
        """Parse VLM response to structured format"""
        # Try to extract JSON from response
        response_text = response_text.strip()

        # Remove markdown code fences if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        try:
            data = json.loads(response_text)
            condition_label = self._normalize_condition_label(str(data.get("condition", "Average")))
            damage = self._normalize_damage(str(data.get("damage", "Not Broken")))
            working_condition = "damaged" if condition_label == "Bad" or damage == "Broken" else "working"
            return VLMResult(
                object_name=str(data.get("object", "electronic component")).strip(),
                condition=working_condition,
                condition_label=condition_label,
                damage=damage,
                confidence=max(0.0, min(1.0, float(data.get("confidence", 0.65)))),
                suggestion=str(data.get("suggestion", f"Condition {condition_label}; damage {damage}.")).strip(),
                eco_score=max(0, min(100, int(data.get("eco_score", 60)))),
                damage_indicators=self._extract_damage_indicators(
                    str(data.get("suggestion", "")),
                    str(data.get("object", "")),
                    str(data.get("damage", "")),
                ),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse VLM response: {e}. Using fallback.")
            return self._fallback_analysis(b"")

    def _normalize_condition_label(self, condition: str) -> str:
        """Normalize condition to Good/Average/Bad for UI consistency."""
        condition = condition.lower().strip()
        mapping = {
            "good": "Good",
            "excellent": "Good",
            "average": "Average",
            "fair": "Average",
            "poor": "Bad",
            "bad": "Bad",
        }
        if condition in mapping:
            return mapping[condition]
        if "poor" in condition or "bad" in condition or "broken" in condition or "major" in condition:
            return "Bad"
        if "average" in condition or "minor" in condition or "wear" in condition:
            return "Average"
        if "good" in condition or "clean" in condition:
            return "Good"
        return "Average"

    def _normalize_damage(self, damage: str) -> str:
        value = damage.lower().strip()
        if value in {"broken", "yes", "damaged"}:
            return "Broken"
        if value in {"not broken", "no", "not_broken", "intact"}:
            return "Not Broken"
        if "broken" in value and "not" not in value:
            return "Broken"
        return "Not Broken"

    def _extract_damage_indicators(self, *texts: str) -> list[str]:
        indicators = []
        allowed = {
            "crack": "cracks",
            "cracks": "cracks",
            "burn": "burns",
            "burns": "burns",
            "broken": "broken parts",
            "broken part": "broken parts",
            "broken parts": "broken parts",
            "exposed wire": "exposed wires",
            "exposed wires": "exposed wires",
            "missing component": "missing components",
            "missing components": "missing components",
        }
        haystack = " ".join(texts).lower()
        for raw, normalized in allowed.items():
            if raw in haystack and normalized not in indicators:
                indicators.append(normalized)
        return indicators

    def _fallback_analysis(self, image_bytes: bytes) -> VLMResult:
        """
        Fallback analysis using image properties when VLM is unavailable.

        This is deterministic and doesn't require API calls.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("L")
            arr = np.asarray(image, dtype=np.uint8)
            brightness = float(arr.mean())
            contrast = float(arr.std())

            # Crack-like cues: high-frequency edges + dark pixels + strong local gradients.
            gx = np.diff(arr.astype(np.float32), axis=1, prepend=arr[:, :1])
            gy = np.diff(arr.astype(np.float32), axis=0, prepend=arr[:1, :])
            grad = np.sqrt(gx * gx + gy * gy)
            strong_edge_ratio = float((grad > 45).mean())
            dark_ratio = float((arr < 40).mean())
            bright_ratio = float((arr > 220).mean())

            damage_score = (strong_edge_ratio * 0.55) + (dark_ratio * 0.30) + (bright_ratio * 0.15)
            is_broken = damage_score > 0.24 or (contrast > 62 and dark_ratio > 0.08)

            if is_broken:
                damage = "Broken"
                condition_label = "Bad"
                condition = "damaged"
                confidence = max(0.58, min(0.82, 0.55 + damage_score))
                suggestion = (
                    "Fallback VLM detected heavy visual damage cues (crack/edge density contrast). "
                    "Treat as Broken until heavy model confirmation."
                )
                indicators = ["cracks"] if strong_edge_ratio > 0.22 else ["broken parts"]
                eco_score = 45
            else:
                damage = "Not Broken"
                if brightness > 145 and contrast < 48:
                    condition_label = "Good"
                    eco_score = 78
                else:
                    condition_label = "Average"
                    eco_score = 64
                condition = "working"
                confidence = 0.56 if condition_label == "Good" else 0.52
                suggestion = "Fallback VLM used; no strong broken-device cues detected."
                indicators = []

            return VLMResult(
                object_name="electronic component",
                condition=condition,
                condition_label=condition_label,
                damage=damage,
                confidence=confidence,
                suggestion=suggestion,
                eco_score=eco_score,
                damage_indicators=indicators,
            )
        except Exception:
            return VLMResult(
                object_name="electronic component",
                condition="damaged",
                condition_label="Bad",
                damage="Broken",
                confidence=0.45,
                suggestion="Fallback VLM failed to parse image; marking as potentially Broken for safety.",
                eco_score=50,
                damage_indicators=["broken parts"],
            )


# Create singleton instance
_vlm_instance: Optional[VLMAnalyzer] = None


def get_vlm_analyzer() -> VLMAnalyzer:
    """Get or create VLM analyzer instance (singleton pattern)"""
    global _vlm_instance
    if _vlm_instance is None:
        _vlm_instance = VLMAnalyzer()
    return _vlm_instance
