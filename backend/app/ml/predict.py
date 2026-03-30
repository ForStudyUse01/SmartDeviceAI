from __future__ import annotations

from dataclasses import dataclass

from app.ml.model_loader import model_bundle, torch


@dataclass(frozen=True)
class ComponentProfile:
    metals: dict[str, str]
    risk: str
    device_health: int
    resale_value: int
    co2_saved: float
    lifecycle_completion: int
    status: dict[str, bool]


COMPONENT_PROFILES: dict[str, ComponentProfile] = {
    "PCB": ComponentProfile(
        metals={"gold": "0.03g", "copper": "120g"},
        risk="Medium",
        device_health=78,
        resale_value=4200,
        co2_saved=12.4,
        lifecycle_completion=64,
        status={"repairable": True, "hazardous": False, "recyclable": True},
    ),
    "battery": ComponentProfile(
        metals={"gold": "0.00g", "copper": "40g"},
        risk="High",
        device_health=62,
        resale_value=1600,
        co2_saved=8.3,
        lifecycle_completion=48,
        status={"repairable": False, "hazardous": True, "recyclable": True},
    ),
    "wire": ComponentProfile(
        metals={"gold": "0.00g", "copper": "85g"},
        risk="Low",
        device_health=90,
        resale_value=900,
        co2_saved=5.2,
        lifecycle_completion=72,
        status={"repairable": True, "hazardous": False, "recyclable": True},
    ),
    "mobile": ComponentProfile(
        metals={"gold": "0.08g", "copper": "150g"},
        risk="Medium",
        device_health=82,
        resale_value=6200,
        co2_saved=15.6,
        lifecycle_completion=66,
        status={"repairable": True, "hazardous": False, "recyclable": True},
    ),
    "charger": ComponentProfile(
        metals={"gold": "0.00g", "copper": "60g"},
        risk="Low",
        device_health=74,
        resale_value=1100,
        co2_saved=4.7,
        lifecycle_completion=57,
        status={"repairable": True, "hazardous": False, "recyclable": True},
    ),
    "unknown": ComponentProfile(
        metals={"gold": "0.00g", "copper": "20g"},
        risk="Medium",
        device_health=35,
        resale_value=400,
        co2_saved=2.1,
        lifecycle_completion=25,
        status={"repairable": False, "hazardous": True, "recyclable": False},
    ),
}


def _parse_grams(raw: str) -> float:
    return float(raw.replace("g", ""))


def _map_imagenet_prediction(label: str) -> str:
    lowered = label.lower()
    for keyword, component in model_bundle.keyword_map.items():
        if keyword in lowered:
            return component
    return "unknown"


def classify_component(image_bytes: bytes) -> str:
    image = model_bundle.open_image(image_bytes)

    if model_bundle.image_model is None or model_bundle.preprocess is None or model_bundle.weights_meta is None or torch is None:
        filename_hint = getattr(image, "filename", "").lower()
        if "battery" in filename_hint:
            return "battery"
        return "PCB"

    tensor = model_bundle.preprocess(image).unsqueeze(0)
    with torch.no_grad():
        prediction = model_bundle.image_model(tensor)

    index = int(prediction.argmax(1).item())
    categories = model_bundle.weights_meta["categories"]
    predicted_label = categories[index]
    return _map_imagenet_prediction(predicted_label)


def predict_scan(image_bytes: bytes) -> dict:
    component = classify_component(image_bytes)
    profile = COMPONENT_PROFILES[component]
    gold = _parse_grams(profile.metals["gold"])
    copper = _parse_grams(profile.metals["copper"])
    predicted_value = int(
        round(
            model_bundle.value_baseline[component]
            + gold * 1800
            + copper * 0.12
            + profile.device_health * 0.35
            + profile.lifecycle_completion * 0.4
        )
    )

    return {
        "component": component,
        "metals": profile.metals,
        "value": predicted_value,
        "risk": profile.risk,
        "deviceHealth": profile.device_health,
        "resaleValue": profile.resale_value,
        "co2Saved": profile.co2_saved,
        "lifecycleCompletion": profile.lifecycle_completion,
        "status": profile.status,
    }
