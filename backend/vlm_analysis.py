from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from typing import Iterable

from openai import OpenAI
from PIL import Image, ImageStat

from utils import image_bytes_to_data_url, majority_vote, normalize_device_label


PROMPT = """Analyze this device image:

* identify device type
* estimate condition (Excellent, Good, Fair, Poor)
* detect damages (scratches, cracks, missing parts)
* give confidence score (0–100)
Return JSON only."""

HYBRID_PROMPT = """Analyze this cropped image of an electronic device or component.

Return a JSON with EXACTLY these keys:
- "object": string (identify the component/device, e.g. "cell phone", "battery", "laptop", "pcb")
- "condition": string (e.g. "working", "partially damaged", "damaged", "scrap", "Fair")
- "suggestion": string (recycling or repair advice, e.g. "salvage motherboard and recycle battery")
- "eco_score": integer (0 to 100 based on recyclability)

Return JSON only."""


@dataclass
class VisionResult:
    device_type: str
    condition: str
    damages: list[str]
    confidence: float


@dataclass
class HybridVisionResult:
    object_name: str
    condition: str
    suggestion: str
    eco_score: int


class VLMAnalyzer:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_VLM_MODEL", "gpt-4.1-mini")

    def analyze_single(self, image_bytes: bytes, mime_type: str) -> VisionResult:
        if self.client is None:
            return self._analyze_single_fallback(image_bytes)

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": PROMPT},
                        {
                            "type": "input_image",
                            "image_url": image_bytes_to_data_url(image_bytes, mime_type),
                        },
                    ],
                }
            ],
        )
        text = response.output_text.strip()
        payload = json.loads(text)
        return VisionResult(
            device_type=normalize_device_label(payload.get("device_type", "unknown")),
            condition=payload.get("condition", "Fair"),
            damages=list(payload.get("damages", [])),
            confidence=float(payload.get("confidence", 50)),
        )

    def analyze_crop(self, image_bytes: bytes, mime_type: str) -> HybridVisionResult:
        if self.client is None:
            return self._analyze_crop_fallback(image_bytes)

        if hasattr(self.client, "responses"):
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": HYBRID_PROMPT},
                            {
                                "type": "input_image",
                                "image_url": image_bytes_to_data_url(image_bytes, mime_type),
                            },
                        ],
                    }
                ],
            )
            text = response.output_text.strip()
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": HYBRID_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_bytes_to_data_url(image_bytes, mime_type)},
                            },
                        ],
                    }
                ],
            )
            text = response.choices[0].message.content.strip()

        # Remove markdown fences if present
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            payload = json.loads(text)
        except Exception:
            payload = {}

        return HybridVisionResult(
            object_name=payload.get("object", "unknown object"),
            condition=payload.get("condition", "unknown condition"),
            suggestion=payload.get("suggestion", "No recycling advice available."),
            eco_score=int(payload.get("eco_score", 50)),
        )

    def _analyze_single_fallback(self, image_bytes: bytes) -> VisionResult:
        """Provide a deterministic local fallback when the VLM API is unavailable."""
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("L")
            brightness = ImageStat.Stat(image).mean[0]
            width, height = image.size
        except Exception:
            brightness = 128
            width, height = 128, 128

        if brightness >= 175:
            condition = "Excellent"
            confidence = 72
            damages = []
        elif brightness >= 125:
            condition = "Good"
            confidence = 66
            damages = ["minor wear"]
        elif brightness >= 80:
            condition = "Fair"
            confidence = 60
            damages = ["visible scratches"]
        else:
            condition = "Poor"
            confidence = 54
            damages = ["visible scratches", "possible dents"]

        if min(width, height) < 300 and "possible dents" not in damages:
            damages.append("low-detail image")

        return VisionResult(
            device_type=normalize_device_label("unknown"),
            condition=condition,
            damages=damages,
            confidence=confidence,
        )

    def _analyze_crop_fallback(self, image_bytes: bytes) -> HybridVisionResult:
        """Provide a deterministic local fallback when the VLM API is unavailable for crops."""
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("L")
            brightness = ImageStat.Stat(image).mean[0]
        except Exception:
            brightness = 128

        condition = "working" if brightness >= 125 else "damaged"
        eco_score = 85 if brightness >= 125 else 40
        suggestion = "Perform data wipe and resell." if condition == "working" else "Salvage reusable metals and recycle."

        return HybridVisionResult(
            object_name="electronic component",
            condition=condition,
            suggestion=suggestion,
            eco_score=eco_score,
        )

    def analyze_many(self, images: Iterable[tuple[bytes, str]]) -> tuple[str, float, list[str], list[VisionResult]]:
        results = [self.analyze_single(image_bytes, mime_type) for image_bytes, mime_type in images]
        ai_condition = majority_vote([item.condition for item in results], default="Fair")
        average_confidence = round(sum(item.confidence for item in results) / max(len(results), 1), 2)
        damages = sorted({damage for item in results for damage in item.damages})
        return ai_condition, average_confidence, damages, results
