"""Utility functions for e-waste detection pipeline"""

from __future__ import annotations

import base64
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional


def image_bytes_to_data_url(image_bytes: bytes, mime_type: str) -> str:
    """Convert image bytes to data URL for APIs"""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def majority_vote(values: Iterable[str], default: str = "unknown") -> str:
    """Get most common value from iterable"""
    items = [value for value in values if value]
    if not items:
        return default
    return Counter(items).most_common(1)[0][0]


def normalize_device_label(label: str) -> str:
    """Normalize device labels to standard format"""
    value = str(label or "").strip().lower()
    aliases = {
        "cell phone": "phone",
        "mobile": "phone",
        "smartphone": "phone",
        "notebook": "laptop",
        "computer": "laptop",
        "pc": "laptop",
        "tab": "tablet",
        "ipad": "tablet",
        "power bank": "powerbank",
        "charger adapter": "charger",
        "adapter": "charger",
        "usb cable": "wire",
        "hdmi": "wire",
        "cable": "wire",
        "circuit board": "pcb",
        "motherboard": "pcb",
        "board": "pcb",
        "battery pack": "battery",
        "li-ion": "battery",
    }
    normalized = aliases.get(value, value or "unknown")
    supported = {
        "phone", "laptop", "tablet", "charger", "powerbank", "pcb",
        "battery", "wire", "unknown", "electronic device", "e-waste component"
    }
    return normalized if normalized in supported else "unknown"


def build_explanation(
    mismatch_messages: list[str],
    damages: list[str],
    trust_score: int,
    detected_device: str,
    ai_condition: str,
) -> str:
    """Build explanation string from analysis results"""
    details: list[str] = []
    if mismatch_messages:
        details.extend(mismatch_messages)
    if damages:
        details.append(f"Damages found: {', '.join(damages)}")
    details.append(f"Detected device: {detected_device}")
    details.append(f"AI condition: {ai_condition}")
    details.append(f"Trust score after verification: {trust_score}")
    return " | ".join(details)


def save_analysis_result(result: dict, output_path: str) -> bool:
    """
    Save analysis result to JSON file.

    Args:
        result: Analysis result dictionary
        output_path: Path to save JSON

    Returns:
        True if successful
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save result: {e}")
        return False


def load_analysis_result(input_path: str) -> Optional[dict]:
    """
    Load analysis result from JSON file.

    Args:
        input_path: Path to JSON file

    Returns:
        Loaded dictionary or None if failed
    """
    try:
        with open(input_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load result: {e}")
        return None


def validate_data_yaml(yaml_path: str) -> tuple[bool, list[str]]:
    """
    Validate data.yaml for YOLO training.

    Args:
        yaml_path: Path to data.yaml

    Returns:
        (is_valid, list of error messages)
    """
    errors = []
    yaml_file = Path(yaml_path)

    if not yaml_file.exists():
        errors.append(f"File not found: {yaml_path}")
        return False, errors

    try:
        import yaml
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)

        # Check required fields
        required_fields = ["path", "train", "val", "nc", "names"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Validate paths
        base_path = Path(data.get("path", ""))
        train_path = base_path / data.get("train", "")
        val_path = base_path / data.get("val", "")

        if not train_path.exists():
            errors.append(f"Train path does not exist: {train_path}")
        if not val_path.exists():
            errors.append(f"Val path does not exist: {val_path}")

        # Check number of classes
        nc = data.get("nc", 0)
        names = data.get("names", [])
        if len(names) != nc:
            errors.append(f"Number of classes ({nc}) doesn't match names ({len(names)})")

        return len(errors) == 0, errors

    except Exception as e:
        errors.append(f"Failed to parse YAML: {e}")
        return False, errors


def format_analysis_for_display(result: Any) -> dict:
    """
    Format analysis result for frontend display.

    Args:
        result: PipelineResult or BatchResult object

    Returns:
        Formatted dictionary
    """
    from dataclasses import asdict

    data = asdict(result) if hasattr(result, "__dataclass_fields__") else result
    return {
        "data": data,
        "formatted": True,
    }

