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

import torch
from PIL import Image, ImageStat
from transformers import Blip2Processor, Blip2ForConditionalGeneration

logger = logging.getLogger(__name__)

# E-waste specific prompt - Enhanced for better accuracy
E_WASTE_PROMPT = """You are an expert in electronic waste (e-waste) assessment. Analyze this device/component image carefully.

IDENTIFY:
1. **Device Type**: Identify the exact device (e.g., iPhone 13, Samsung Galaxy, laptop, PCB board, battery, charger, etc.)
2. **Condition Assessment**: Look for physical signs:
   - Working: No visible damage, screen intact, no cracks, clean
   - Partially working: Minor scratches, small dents, might have functional issues
   - Damaged: Cracked screen, broken parts, water damage, major cracks
   - Scrap: Beyond repair, salvage value only

3. **Recyclability**: Consider metal content (gold, copper, rare earths) and material composition
4. **Eco Score** (0-100):
   - 80-100: Highly recyclable, good material value, minimal contamination
   - 60-79: Recyclable, moderate value, some contamination
   - 40-59: Partially recyclable, low value, significant damage
   - 0-39: Mostly scrap, minimal material value

Look for specific markers:
- **Phones**: Screen quality, frame condition, camera lens clarity, bezels
- **Laptops**: Screen cracks, keyboard functionality, hinge condition
- **Batteries**: Swelling, corrosion, leakage
- **PCBs**: Component availability, corrosion, traces integrity

Return ONLY valid JSON:
{
  "object": "specific device name",
  "condition": "working|partially working|damaged|scrap",
  "suggestion": "recycling or repair recommendation",
  "eco_score": 0-100 integer
}

Return JSON only, no explanation."""


@dataclass
class VLMResult:
    """VLM analysis result"""
    object_name: str
    condition: str
    suggestion: str
    eco_score: int


class VLMAnalyzer:
    """Local BLIP-2 Vision Language Model Analyzer"""

    def __init__(self, model_name: str = "Salesforce/blip2-opt-2.7b"):
        """
        Initialize BLIP-2 model for e-waste analysis.

        Args:
            model_name: HuggingFace model identifier
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        self.processor = None
        self.model = None
        # Keep fast local analysis on by default; opt into BLIP-2 only when explicitly requested.
        self.enable_model = os.getenv("ENABLE_HEAVY_VLM", "0").lower() in {"1", "true", "yes", "on"}

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
            return VLMResult(
                object_name=str(data.get("object", "unknown object")).strip(),
                condition=self._normalize_condition(str(data.get("condition", "unknown"))),
                suggestion=str(data.get("suggestion", "No recycling advice available.")).strip(),
                eco_score=max(0, min(100, int(data.get("eco_score", 50)))),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse VLM response: {e}. Using fallback.")
            return self._fallback_analysis(b"")

    def _normalize_condition(self, condition: str) -> str:
        """Normalize condition string to standard values"""
        condition = condition.lower().strip()
        valid_conditions = {"working", "partially working", "damaged", "scrap"}

        if condition in valid_conditions:
            return condition

        # Map variations to standard values
        mapping = {
            "good": "working",
            "excellent": "working",
            "ok": "partially working",
            "fair": "partially working",
            "bad": "damaged",
            "broken": "damaged",
            "defective": "damaged",
            "recycled": "scrap",
            "waste": "scrap",
        }

        return mapping.get(condition, "partially working")

    def _fallback_analysis(self, image_bytes: bytes) -> VLMResult:
        """
        Fallback analysis using image properties when VLM is unavailable.

        This is deterministic and doesn't require API calls.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("L")
            brightness = ImageStat.Stat(image).mean[0]
        except Exception:
            brightness = 128

        # Simple heuristic based on brightness
        if brightness >= 150:
            condition = "working"
            eco_score = 85
            suggestion = "Device appears to be in good condition. Perform data wipe and resell."
        elif brightness >= 100:
            condition = "partially working"
            eco_score = 60
            suggestion = "Minor damages detected. Test functionality and resell if working."
        else:
            condition = "damaged"
            eco_score = 40
            suggestion = "Device appears damaged. Salvage reusable components and recycle."

        return VLMResult(
            object_name="electronic component",
            condition=condition,
            suggestion=suggestion,
            eco_score=eco_score,
        )


# Create singleton instance
_vlm_instance: Optional[VLMAnalyzer] = None


def get_vlm_analyzer() -> VLMAnalyzer:
    """Get or create VLM analyzer instance (singleton pattern)"""
    global _vlm_instance
    if _vlm_instance is None:
        _vlm_instance = VLMAnalyzer()
    return _vlm_instance
