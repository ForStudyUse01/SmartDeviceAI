from __future__ import annotations

import io
import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from PIL import Image

from database.sqlite_store import get_store
from services.ai_service import get_ai_service


logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai-inference"])


class DetectResponse(BaseModel):
    status: str
    image_name: str
    detections: list[dict[str, Any]]
    model_path: str
    device: str


class ExplainResponse(BaseModel):
    status: str
    image_name: str
    detections: list[dict[str, Any]]
    caption: str
    description: str
    model_path: str
    device: str


@router.post("/detect", response_model=DetectResponse)
async def detect_objects(
    file: UploadFile = File(...),
    conf_threshold: float = Query(0.25, ge=0.0, le=1.0),
):
    """Detect objects with YOLO and return bounding boxes + labels."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        ai = get_ai_service()
        image = Image.open(io.BytesIO(content)).convert("RGB")
        detections = ai.detect(image=image, conf_threshold=conf_threshold)
        get_store().log_result(
            endpoint="/detect",
            image_name=file.filename,
            detections=detections,
            explanation=None,
            model_path=str(ai.yolo_model_path),
            device=ai.device_str,
        )
        return DetectResponse(
            status="success",
            image_name=file.filename,
            detections=detections,
            model_path=str(ai.yolo_model_path),
            device=ai.device_str,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Detect endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")


@router.post("/explain", response_model=ExplainResponse)
async def explain_image(
    file: UploadFile = File(...),
    conf_threshold: float = Query(0.25, ge=0.0, le=1.0),
):
    """Run YOLO detection and generate a VLM explanation."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        ai = get_ai_service()
        image = Image.open(io.BytesIO(content)).convert("RGB")
        detections = ai.detect(image=image, conf_threshold=conf_threshold)
        explanation = ai.explain(image=image, detections=detections)
        get_store().log_result(
            endpoint="/explain",
            image_name=file.filename,
            detections=detections,
            explanation=explanation["description"],
            model_path=str(ai.yolo_model_path),
            device=ai.device_str,
        )
        return ExplainResponse(
            status="success",
            image_name=file.filename,
            detections=detections,
            caption=explanation["caption"],
            description=explanation["description"],
            model_path=str(ai.yolo_model_path),
            device=ai.device_str,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Explain endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Explanation failed: {e}")

