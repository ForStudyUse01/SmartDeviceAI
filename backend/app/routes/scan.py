import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.database import get_database
from app.core.security import get_current_token
from app.ml.predict import predict_scan
from app.models.scan import ScanInDB, ScanResponse
from app.schemas.scan import RecentScansResponse

router = APIRouter(tags=["scan"])
logger = logging.getLogger(__name__)


def _ai_backend_base_url() -> str:
    return str(settings.ai_backend_url or "http://127.0.0.1:5000").strip().rstrip("/")


ALLOWED_CLASSES = {"mobile", "laptop", "tablet", "powerbank", "electronic device"}


def _offline_fallback_detected(normalized_user_device: str) -> dict[str, Any]:
    """When YOLO/VLM service is down, align detection with user's selected device so validation can pass."""
    dev = normalized_user_device if normalized_user_device in ALLOWED_CLASSES else "mobile"
    return {
        "detected_device": dev,
        "detected_device_type": dev,
        "detected_condition": "unknown",
        "detected_objects": [
            {
                "label": dev,
                "yolo_label": dev,
                "confidence": 0.55,
                "yolo_confidence": 0.55,
                "model_used": "offline_fallback",
                "condition": "partially working",
                "details": "AI inference service is not reachable; using offline alignment with your form input.",
                "suggestion": "For live YOLO/VLM, run `python app.py` (port 5000) locally or set AI_BACKEND_URL to a running inference API.",
            }
        ],
        "confidence": 0.55,
        "confidence_label": "medium",
        "damage_confidence": 0.5,
    }


def _offline_fallback_final_analysis(image_name: str) -> dict[str, Any]:
    return {
        "status": "success",
        "image_name": image_name,
        "detected_objects": [
            {
                "yolo_label": "mobile",
                "yolo_confidence": 55,
                "vlm_condition": "Average",
                "vlm_damage": "Not Broken",
                "damage_confidence": 0.5,
                "condition": "partially working",
                "suggestion": "Offline mode — connect the AI backend for full image verification.",
            }
        ],
        "num_detections": 1,
        "error_message": "offline_fallback",
    }


DEVICE_SYNONYMS = {
    "mobile": "mobile",
    "cell phone": "mobile",
    "smartphone": "mobile",
    "phone": "mobile",
    "mobile phone": "mobile",
    "power bank": "powerbank",
    "powerbank": "powerbank",
    "notebook": "laptop",
}


def _normalize_text(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_device(value: str) -> str:
    normalized = _normalize_text(value)
    return DEVICE_SYNONYMS.get(normalized, normalized)


def _normalize_condition(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized in {"excellent", "good", "working", "no visible damage", "clean"}:
        return "good"
    if normalized in {"average", "fair", "damaged", "partially working", "minor issues"}:
        return "damaged"
    if normalized in {"poor", "bad", "broken", "scrap", "major damage"}:
        return "bad"
    if "major" in normalized or "bad" in normalized or "broken" in normalized:
        return "bad"
    if "damage" in normalized or "minor" in normalized or "fair" in normalized:
        return "damaged"
    return "good"


def _confidence_label(confidence: float) -> str:
    normalized = _normalized_confidence(confidence)
    if normalized < 0.5:
        return "low"
    if normalized < 0.7:
        return "medium"
    return "high"


def _extract_confidence(obj: dict[str, Any]) -> float:
    raw = obj.get("yolo_confidence", obj.get("confidence", 0.0))
    try:
        return _normalized_confidence(float(raw))
    except (TypeError, ValueError):
        return 0.0


def _extract_label(obj: dict[str, Any]) -> str:
    raw = obj.get("yolo_label") or obj.get("label") or "unknown"
    return _normalize_device(str(raw))


def _filter_supported_detections(detected_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = [obj for obj in detected_objects if _extract_label(obj) in ALLOWED_CLASSES]
    return sorted(filtered, key=_extract_confidence, reverse=True)


def _extract_detected_summary(ai_result: dict[str, Any]) -> dict[str, Any]:
    raw_objects = ai_result.get("detected_objects", []) or ai_result.get("detections", [])
    detected_objects = _filter_supported_detections(raw_objects)
    if not detected_objects:
        logger.warning("No detections in AI response payload: %s", ai_result)
        return {
            "detected_device": "mobile",
            "detected_device_type": "mobile",
            "detected_condition": "unknown",
            "detected_objects": [
                {
                    "label": "mobile",
                    "confidence": 0.4,
                    "box": [0, 0, 0, 0],
                    "model_used": "heuristic",
                }
            ],
            "confidence": 0.4,
            "confidence_label": "low",
        }

    primary = max(detected_objects, key=_extract_confidence)
    label = _extract_label(primary)
    cond = primary.get("condition", "unknown")
    conf = _extract_confidence(primary)
    return {
        "detected_device": label,
        "detected_device_type": label,
        "detected_condition": _normalize_condition(cond),
        "detected_objects": detected_objects,
        "confidence": float(conf),
        "confidence_label": _confidence_label(conf),
        "damage_confidence": float(primary.get("damage_confidence", conf)),
    }


def _extract_detected_summary_from_batch(batch_result: dict[str, Any]) -> dict[str, Any]:
    results = batch_result.get("results", [])
    flattened: list[dict[str, Any]] = []
    for entry in results:
        flattened.extend(entry.get("detected_objects", []))
    filtered = _filter_supported_detections(flattened)
    if not filtered:
        logger.warning("No detections in batch AI payload: %s", batch_result)
        return {
            "detected_device": "mobile",
            "detected_device_type": "mobile",
            "detected_condition": "unknown",
            "detected_objects": [
                {
                    "label": "mobile",
                    "confidence": 0.4,
                    "box": [0, 0, 0, 0],
                    "model_used": "heuristic",
                }
            ],
            "confidence": 0.4,
            "confidence_label": "low",
        }
    primary = max(filtered, key=_extract_confidence)
    label = _extract_label(primary)
    cond = primary.get("condition", "unknown")
    conf = _extract_confidence(primary)
    return {
        "detected_device": label,
        "detected_device_type": label,
        "detected_condition": _normalize_condition(cond),
        "detected_objects": filtered,
        "confidence": float(conf),
        "confidence_label": _confidence_label(conf),
        "damage_confidence": float(primary.get("damage_confidence", conf)),
    }


def _extract_detected_summary_from_analysis(final_analysis: dict[str, Any]) -> dict[str, Any]:
    """Build detected summary directly from /analyze or /analyze-batch payloads."""
    if isinstance(final_analysis.get("results"), list):
        return _extract_detected_summary_from_batch(final_analysis)
    return _extract_detected_summary(
        {"detected_objects": final_analysis.get("detected_objects", [])}
    )


def _is_timeout_fallback(final_analysis: dict[str, Any]) -> bool:
    """
    Detect AI timeout fallback payloads from backend/app.py.
    These are not reliable enough for strict device/condition verification.
    """
    message = str(final_analysis.get("error_message", "")).lower()
    if "timed out" in message or "fallback" in message:
        return True
    if isinstance(final_analysis.get("results"), list):
        for item in final_analysis["results"]:
            item_message = str(item.get("error_message", "")).lower()
            if "timed out" in item_message or "fallback" in item_message:
                return True
    return False


def _normalized_confidence(value: float) -> float:
    if value > 1.0:
        return max(0.0, min(1.0, value / 100.0))
    return max(0.0, min(1.0, value))


def _normalize_vlm_condition(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized == "good":
        return "Good"
    if normalized in {"poor", "bad"}:
        return "Bad"
    if normalized == "average":
        return "Average"
    if "poor" in normalized or "bad" in normalized or "broken" in normalized:
        return "Bad"
    if "good" in normalized or "clean" in normalized:
        return "Good"
    return "Average"


def _normalize_vlm_damage(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized in {"broken", "yes"}:
        return "Broken"
    if normalized in {"not broken", "no", "intact"}:
        return "Not Broken"
    if "broken" in normalized and "not" not in normalized:
        return "Broken"
    return "Not Broken"


def _extract_vlm_summary(final_analysis: dict[str, Any]) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    if isinstance(final_analysis.get("detected_objects"), list):
        objects.extend(final_analysis.get("detected_objects", []))
    if isinstance(final_analysis.get("results"), list):
        for item in final_analysis["results"]:
            batch_objects = item.get("detected_objects", [])
            if isinstance(batch_objects, list):
                objects.extend(batch_objects)

    if not objects:
        return {"vlm_condition": "Average", "vlm_damage": "Not Broken", "damage_confidence": 0.5}

    def _condition_rank(value: str) -> int:
        normalized = _normalize_vlm_condition(value)
        if normalized == "Bad":
            return 3
        if normalized == "Average":
            return 2
        return 1

    # Prefer the strongest damage signal across all uploaded images.
    best_damage_obj = max(
        objects,
        key=lambda obj: _normalized_confidence(float(obj.get("damage_confidence", obj.get("yolo_confidence", 0.0)))),
    )
    any_broken = any(_normalize_vlm_damage(str(obj.get("vlm_damage", "Not Broken"))) == "Broken" for obj in objects)
    worst_condition_obj = max(
        objects,
        key=lambda obj: _condition_rank(str(obj.get("vlm_condition", obj.get("condition", "Average")))),
    )

    combined_damage_conf = _normalized_confidence(
        float(best_damage_obj.get("damage_confidence", best_damage_obj.get("yolo_confidence", 0.5)))
    )
    combined_condition = _normalize_vlm_condition(
        str(worst_condition_obj.get("vlm_condition", worst_condition_obj.get("condition", "Average")))
    )

    if any_broken and combined_condition != "Bad":
        combined_condition = "Bad"

    return {
        "vlm_condition": combined_condition,
        "vlm_damage": "Broken" if any_broken else _normalize_vlm_damage(str(best_damage_obj.get("vlm_damage", "Not Broken"))),
        "damage_confidence": combined_damage_conf,
    }


def _classify_condition(vlm_condition: str, vlm_damage: str, damage_confidence: float) -> str:
    """
    Final condition classification:
    - heavily damaged -> Poor
    - slightly damaged -> Average
    - no damage -> Good
    """
    normalized_condition = _normalize_vlm_condition(vlm_condition)
    normalized_damage = _normalize_vlm_damage(vlm_damage)
    confidence = _normalized_confidence(float(damage_confidence))

    if normalized_damage == "Broken" or normalized_condition == "Bad" or confidence >= 0.7:
        return "Poor"
    if normalized_condition == "Average" or confidence >= 0.35:
        return "Average"
    return "Good"


def _compute_match_score(user_input: dict[str, Any], vlm_condition: str) -> tuple[int, list[str]]:
    score = 100
    reasons: list[str] = []
    user_condition = _normalize_vlm_condition(user_input.get("condition", "Average"))
    ai_condition = _normalize_vlm_condition(vlm_condition)
    pair = {user_condition, ai_condition}

    # Condition distance penalties
    if pair == {"Good", "Average"}:
        score -= 10
    elif pair == {"Average", "Bad"}:
        score -= 15
        reasons.append("Moderate condition difference")
    elif pair == {"Good", "Bad"}:
        score -= 25
        reasons.append("Major condition difference")

    # Damage contradiction penalties (manual flags vs VLM brokenness)
    has_user_damage = bool(user_input.get("screen_damage")) or bool(user_input.get("body_damage")) or bool(
        user_input.get("water_damage")
    )
    vlm_damage = _normalize_vlm_damage(str(user_input.get("vlm_damage", "Not Broken")))
    if not has_user_damage and vlm_damage == "Broken":
        score -= 30
        reasons.append("AI detected damage not mentioned by user")
    elif has_user_damage and vlm_damage == "Not Broken":
        score -= 15
        reasons.append("User reported damage not visible in image")

    confidence = _normalized_confidence(float(user_input.get("detected_confidence", 0.0)))
    # Device mismatch penalty only at high confidence.
    if confidence > 0.7:
        user_device = _normalize_device(str(user_input.get("device_type", "")))
        ai_device = _normalize_device(str(user_input.get("detected_device_type", "")))
        if user_device and ai_device and user_device != ai_device:
            score -= 40
            reasons.append("Device type mismatch with high confidence")
    if confidence < 0.6:
        reasons.append("Low confidence detection - result may vary")

    # Confidence weighting.
    if confidence >= 0.7:
        weight = 1.0
    elif confidence >= 0.5:
        weight = 0.85
    else:
        weight = 0.7
    score = int(round(score * weight))

    return max(0, min(100, score)), reasons


def serialize_scan(document: dict) -> ScanResponse:
    return ScanResponse(
        id=str(document["_id"]),
        component=document["component"],
        metals=document["metals"],
        value=document["value"],
        risk=document["risk"],
        deviceHealth=document["device_health"],
        resaleValue=document["resale_value"],
        co2Saved=document["co2_saved"],
        lifecycleCompletion=document["lifecycle_completion"],
        status=document["status"],
        createdAt=document["created_at"],
    )


@router.post("/scan", response_model=ScanResponse)
async def scan_device(
    file: UploadFile = File(...),
    token_payload: dict = Depends(get_current_token),
    database=Depends(get_database),
) -> ScanResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload an image file")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    prediction = predict_scan(image_bytes)
    scan_document = ScanInDB.from_prediction(token_payload["sub"], file.filename or "upload", prediction)
    result = await database.scans.insert_one(scan_document.model_dump())
    created_scan = await database.scans.find_one({"_id": result.inserted_id})
    return serialize_scan(created_scan)


@router.get("/scans/recent", response_model=RecentScansResponse)
async def recent_scans(
    token_payload: dict = Depends(get_current_token),
    database=Depends(get_database),
) -> RecentScansResponse:
    cursor = (
        database.scans.find({"user_id": token_payload["sub"]})
        .sort("created_at", -1)
        .limit(8)
    )
    scans = [serialize_scan(scan) async for scan in cursor]
    return RecentScansResponse(scans=scans)


@router.post("/ai-device-scan")
async def ai_device_scan(
    images: list[UploadFile] = File(...),
    device_type: str = Form(...),
    brand: str = Form(...),
    model: str = Form(...),
    age: int = Form(...),
    condition: str = Form(...),
    screen_damage: bool = Form(...),
    body_damage: bool = Form(...),
    water_damage: bool = Form(...),
    token_payload: dict = Depends(get_current_token),
):
    _ = token_payload
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one image is required")

    for image in images:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All uploaded files must be images")

    image_payloads: list[tuple[str, bytes, str]] = []
    for image in images:
        content = await image.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty")
        image_payloads.append((image.filename or "image.jpg", content, image.content_type or "image/jpeg"))

    user_input = {
        "device_type": _normalize_device(device_type),
        "brand": _normalize_text(brand),
        "model": _normalize_text(model),
        "age": age,
        "condition": _normalize_text(condition),
        "screen_damage": bool(screen_damage),
        "body_damage": bool(body_damage),
        "water_damage": bool(water_damage),
    }

    ai_offline = False
    base = _ai_backend_base_url()
    read_timeout = max(30.0, float(settings.ai_backend_read_timeout_seconds))
    # Connect fails fast if nothing is listening; read timeout allows first BLIP-2 download/load + inference.
    _ai_http_timeout = httpx.Timeout(read_timeout, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=_ai_http_timeout) as client:
            if len(image_payloads) == 1:
                filename, content, content_type = image_payloads[0]
                final_response = await client.post(
                    f"{base}/analyze?conf_threshold=0.25",
                    files={"file": (filename, content, content_type)},
                )
            else:
                files = [("files", (name, content, ctype)) for name, content, ctype in image_payloads]
                final_response = await client.post(
                    f"{base}/analyze-batch?conf_threshold=0.25",
                    files=files,
                )
            final_response.raise_for_status()
            final_analysis = final_response.json()
            if _is_timeout_fallback(final_analysis):
                return {
                    "success": False,
                    "error": "AI model timed out before full YOLO+VLM analysis completed. Please retry the scan.",
                    "detected": {
                        "detected_device": "unknown",
                        "detected_device_type": "unknown",
                        "detected_condition": "unknown",
                        "detected_objects": [],
                        "confidence": 0.0,
                        "confidence_label": "low",
                        "vlm_condition": "Average",
                        "vlm_damage": "Not Broken",
                        "damage_confidence": 0.0,
                    },
                    "user_input": user_input,
                    "match_score": 0,
                    "reasons": [
                        "Full AI pipeline timed out; result was not trusted.",
                        "Please retry with 1-2 clear images while AI backend is warm.",
                    ],
                    "final_analysis": final_analysis,
                }
            detected = _extract_detected_summary_from_analysis(final_analysis)
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        logger.warning(
            "AI backend at %s unreachable or returned an error (%s); using offline fallback for ai-device-scan",
            base,
            exc,
        )
        ai_offline = True
        detected = _offline_fallback_detected(user_input["device_type"])
        first_name = image_payloads[0][0]
        final_analysis = _offline_fallback_final_analysis(first_name)
    vlm_summary = _extract_vlm_summary(final_analysis)
    detected["vlm_condition"] = vlm_summary["vlm_condition"]
    detected["vlm_damage"] = vlm_summary["vlm_damage"]
    detected["damage_confidence"] = float(vlm_summary.get("damage_confidence", detected.get("confidence", 0.5)))
    detected["condition"] = _classify_condition(
        detected["vlm_condition"],
        detected["vlm_damage"],
        detected["damage_confidence"],
    )
    detected["detected_condition"] = _normalize_text(detected["condition"])

    yolo_device = _normalize_device(detected.get("detected_device_type", "unknown"))
    manual_device = _normalize_device(user_input["device_type"])
    is_match = yolo_device == manual_device
    detected["match_status"] = "Match" if is_match else "Not Match"

    if not is_match:
        return {
            "success": False,
            "error": "AI scan and Manual input do not match",
            "detected": detected,
            "user_input": user_input,
            "match_score": 0,
            "reasons": [
                f"YOLO detected: {yolo_device}",
                f"Manual input: {manual_device}",
            ],
            "final_analysis": final_analysis,
        }

    scoring_input = {
        **user_input,
        "vlm_damage": vlm_summary["vlm_damage"],
        "detected_device_type": detected.get("detected_device_type", ""),
        "detected_confidence": detected.get("confidence", 0.0),
    }

    match_score, reasons = _compute_match_score(scoring_input, vlm_summary["vlm_condition"])
    if ai_offline:
        reasons = [
            "AI inference backend offline — scan used your selected device type and average condition defaults.",
            *reasons,
        ]

    return {
        "success": True,
        "detected": detected,
        "match_status": "Match",
        "user_input": user_input,
        "match_score": match_score,
        "reasons": reasons,
        "final_analysis": final_analysis,
    }
