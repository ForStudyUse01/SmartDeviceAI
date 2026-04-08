import os
from difflib import SequenceMatcher
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.database import get_database
from app.core.security import get_current_token
from app.ml.predict import predict_scan
from app.models.scan import ScanInDB, ScanResponse
from app.schemas.scan import RecentScansResponse

router = APIRouter(tags=["scan"])
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL", "http://127.0.0.1:5000")
logger = logging.getLogger(__name__)
ALLOWED_CLASSES = {"mobile", "laptop", "tablet", "powerbank"}


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
    }


def _normalized_confidence(value: float) -> float:
    if value > 1.0:
        return max(0.0, min(1.0, value / 100.0))
    return max(0.0, min(1.0, value))


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize_device(left), _normalize_device(right)).ratio()


def _collect_detection_text(detected_objects: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for obj in detected_objects:
        chunks.extend(
            [
                str(obj.get("yolo_label", "")),
                str(obj.get("vlm_object", "")),
                str(obj.get("condition", "")),
                str(obj.get("details", "")),
                str(obj.get("suggestion", "")),
            ]
        )
    return " ".join(chunks).lower()


def _has_indicator(detected_objects: list[dict[str, Any]], keywords: tuple[str, ...]) -> bool:
    text_blob = _collect_detection_text(detected_objects)
    return any(keyword in text_blob for keyword in keywords)


def _validate_user_vs_ai(
    user_input: dict[str, Any],
    detected: dict[str, Any],
) -> str | None:
    confidence = _normalized_confidence(float(detected.get("confidence", 0.0)))
    if confidence < 0.5:
        return "Low confidence - try clearer image"

    user_device = _normalize_device(user_input["device_type"])
    ai_device = _normalize_device(detected["detected_device_type"])
    device_similarity = _similarity(user_device, ai_device)
    if device_similarity < 0.7:
        return "User input does not match AI-detected device"

    detected_objects = detected.get("detected_objects", [])
    screen_issue_detected = _has_indicator(
        detected_objects, ("crack", "cracked_screen", "screen damage", "display damage", "broken screen")
    )
    body_issue_detected = _has_indicator(
        detected_objects, ("body defect", "dent", "frame damage", "broken body", "scratch")
    )
    water_issue_detected = _has_indicator(
        detected_objects, ("water", "corrosion", "rust", "liquid damage", "oxidation")
    )

    mismatch_points = 0
    if bool(user_input["screen_damage"]) != bool(screen_issue_detected):
        mismatch_points += 1
    if bool(user_input["body_damage"]) != bool(body_issue_detected):
        mismatch_points += 1
    if bool(user_input["water_damage"]) != bool(water_issue_detected):
        mismatch_points += 1

    # Major mismatch policy: reject if multiple independent checks conflict.
    if mismatch_points >= 2:
        return "User input does not match AI-detected device"

    return None


def _normalize_vlm_condition(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized == "good":
        return "Good"
    if normalized == "poor":
        return "Poor"
    if normalized == "average":
        return "Average"
    if "poor" in normalized or "bad" in normalized or "broken" in normalized:
        return "Poor"
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


def _extract_vlm_summary(final_analysis: dict[str, Any]) -> dict[str, str]:
    first: dict[str, Any] | None = None
    if isinstance(final_analysis.get("detected_objects"), list) and final_analysis.get("detected_objects"):
        first = final_analysis["detected_objects"][0]
    elif isinstance(final_analysis.get("results"), list):
        for item in final_analysis["results"]:
            objects = item.get("detected_objects", [])
            if objects:
                first = objects[0]
                break

    if not first:
        return {"vlm_condition": "Average", "vlm_damage": "Not Broken"}

    return {
        "vlm_condition": _normalize_vlm_condition(str(first.get("vlm_condition", first.get("condition", "Average")))),
        "vlm_damage": _normalize_vlm_damage(str(first.get("vlm_damage", "Not Broken"))),
    }


def _compute_match_score(user_input: dict[str, Any], vlm_condition: str) -> tuple[int, list[str]]:
    score = 100
    reasons: list[str] = []
    user_condition = _normalize_vlm_condition(user_input.get("condition", "Average"))
    ai_condition = _normalize_vlm_condition(vlm_condition)
    pair = {user_condition, ai_condition}

    # Condition distance penalties
    if pair == {"Good", "Average"}:
        score -= 10
        reasons.append("Minor condition difference")
    elif pair == {"Average", "Poor"}:
        score -= 15
        reasons.append("Moderate condition difference")
    elif pair == {"Good", "Poor"}:
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

    async with httpx.AsyncClient(timeout=90.0) as client:
        # Step 1 detection-only pass: use /detect at conf=0.25 for clearer device-confidence extraction.
        detection_payloads: list[dict[str, Any]] = []
        for name, content, ctype in image_payloads:
            detect_response = await client.post(
                f"{AI_BACKEND_URL}/detect?conf_threshold=0.25",
                files={"file": (name, content, ctype)},
            )
            if detect_response.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI backend detect step failed",
                )
            detection_payloads.append(detect_response.json())

        if len(detection_payloads) == 1:
            detected = _extract_detected_summary(detection_payloads[0])
        else:
            batch_like = {"results": [{"detected_objects": d.get("detections", [])} for d in detection_payloads]}
            detected = _extract_detected_summary_from_batch(batch_like)
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

    # Step 4: call the existing hybrid AI pipeline for final analysis.
    async with httpx.AsyncClient(timeout=90.0) as client:
        if len(image_payloads) == 1:
            filename, content, content_type = image_payloads[0]
            final_response = await client.post(
                f"{AI_BACKEND_URL}/analyze?conf_threshold=0.25",
                files={"file": (filename, content, content_type)},
            )
        else:
            files = [("files", (name, content, ctype)) for name, content, ctype in image_payloads]
            final_response = await client.post(
                f"{AI_BACKEND_URL}/analyze-batch?conf_threshold=0.25",
                files=files,
            )
        if final_response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI backend final analysis failed",
            )
        final_analysis = final_response.json()
    vlm_summary = _extract_vlm_summary(final_analysis)
    detected["vlm_condition"] = vlm_summary["vlm_condition"]
    detected["vlm_damage"] = vlm_summary["vlm_damage"]
    scoring_input = {
        **user_input,
        "vlm_damage": vlm_summary["vlm_damage"],
        "detected_device_type": detected.get("detected_device_type", ""),
        "detected_confidence": detected.get("confidence", 0.0),
    }

    match_score, reasons = _compute_match_score(scoring_input, vlm_summary["vlm_condition"])
    validation_error = _validate_user_vs_ai(user_input, detected)
    if validation_error:
        if not detected.get("detected_objects"):
            logger.warning("No YOLO detections; returning heuristic device output.")
        return {
            "success": False,
            "error": validation_error,
            "detected": detected,
            "user_input": user_input,
            "match_score": match_score,
            "reasons": reasons,
        }

    return {
        "success": True,
        "detected": detected,
        "user_input": user_input,
        "match_score": match_score,
        "reasons": reasons,
        "final_analysis": final_analysis,
    }
