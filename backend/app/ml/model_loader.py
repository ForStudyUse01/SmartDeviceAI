from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image

try:
    import torch
    from torchvision import models, transforms
except Exception:  # pragma: no cover - fallback path for environments without torch
    torch = None
    models = None
    transforms = None


class ModelBundle:
    def __init__(self) -> None:
        self.class_labels = ["PCB", "battery", "wire", "mobile", "charger", "unknown"]
        self.keyword_map = {
            "circuit": "PCB",
            "screen": "mobile",
            "cellular": "mobile",
            "battery": "battery",
            "coil": "wire",
            "cable": "wire",
            "charger": "charger",
            "plug": "charger",
        }
        self.image_model: Any | None = None
        self.preprocess: Any | None = None
        self.weights_meta: Any | None = None
        self.component_encoding = {label: index for index, label in enumerate(self.class_labels)}
        self.value_baseline = {
            "PCB": 250,
            "battery": 180,
            "wire": 140,
            "mobile": 510,
            "charger": 120,
            "unknown": 60,
        }
        self._load_classifier()

    def _load_classifier(self) -> None:
        if torch is None or models is None or transforms is None:
            return

        weights = models.MobileNet_V2_Weights.DEFAULT
        self.image_model = models.mobilenet_v2(weights=weights)
        self.image_model.eval()
        self.preprocess = weights.transforms()
        self.weights_meta = weights.meta

    def open_image(self, raw_bytes: bytes) -> Image.Image:
        return Image.open(BytesIO(raw_bytes)).convert("RGB")


model_bundle = ModelBundle()
