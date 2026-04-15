"""
Shared VLM prompt + training target formatting.

Inference (`vlm_model.VLMAnalyzer`) and fine-tuning (`train_vlm.py`) must use the
same user prompt and the same JSON label shape or the model will not learn to emit
parseable answers at runtime.
"""

from __future__ import annotations

import json
from typing import Any

# Must stay in sync with what `VLMAnalyzer.analyze_crop` sends to the processor.
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
  "object": "short device/component label",
  "condition": "...",
  "damage": "...",
  "confidence": 0.0
}
"""


def object_label_for_row(row: dict[str, Any]) -> str:
    """Short object string used in training targets (matches inference expectations)."""
    raw = str(row.get("device_type") or row.get("object") or "unknown").strip().lower()
    if raw in {"mobile", "cell phone", "smartphone", "phone"}:
        return "mobile phone"
    if raw == "laptop":
        return "laptop"
    if raw == "tablet":
        return "tablet"
    if raw in {"powerbank", "power bank"}:
        return "power bank"
    return "electronic device"


def training_target_json(row: dict[str, Any], *, condition: str, damage: str) -> str:
    """Single-line JSON string used as decoder labels during fine-tuning."""
    payload = {
        "object": object_label_for_row(row),
        "condition": condition,
        "damage": damage,
        "confidence": 0.82,
    }
    return json.dumps(payload, ensure_ascii=False)
