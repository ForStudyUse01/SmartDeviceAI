from __future__ import annotations

from dataclasses import dataclass


CONDITION_FACTORS = {
    "Excellent": 1.0,
    "Good": 0.8,
    "Fair": 0.6,
    "Poor": 0.4,
}


BASE_PRICES = {
    "phone": 40000,
    "laptop": 65000,
    "tablet": 30000,
    "charger": 1200,
    "powerbank": 2200,
    "pcb": 0,
}


METAL_RATES = {
    "gold_per_g": 7200,
    "copper_per_g": 0.8,
}


@dataclass
class PricingInput:
    device_type: str
    condition: str
    age: float
    trust_score: int
    metal_value: float = 0.0


def get_age_factor(age: float) -> float:
    if age < 1:
        return 0.9
    if age < 2:
        return 0.7
    if age < 3:
        return 0.5
    return 0.35


def calculate_metal_value(metals: dict[str, str] | None = None) -> float:
    metals = metals or {}
    gold = float(str(metals.get("gold", "0")).replace("g", "") or 0)
    copper = float(str(metals.get("copper", "0")).replace("g", "") or 0)
    return round(gold * METAL_RATES["gold_per_g"] + copper * METAL_RATES["copper_per_g"], 2)


def calculate_final_price(payload: PricingInput) -> float:
    device = payload.device_type.lower()
    condition_factor = CONDITION_FACTORS.get(payload.condition, 0.6)
    trust_factor = payload.trust_score / 100
    metal_value = payload.metal_value

    if device == "pcb":
        return round(metal_value, 2)

    if device in {"charger", "powerbank"}:
        fixed_base = BASE_PRICES.get(device, 1500)
        return round((fixed_base * condition_factor * trust_factor) + metal_value, 2)

    base_price = BASE_PRICES.get(device, 18000)
    age_factor = get_age_factor(payload.age)
    price = (base_price * condition_factor * age_factor * trust_factor) + metal_value
    return round(price, 2)
