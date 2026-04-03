"""
E-waste Detection API (FastAPI)
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pipeline import E_WasteDetectionPipeline, DetectedObject, BatchResult, PipelineResult
from yolo_model import TrainingConfig

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
ANALYSIS_TIMEOUT_SECONDS = float(os.getenv("ANALYSIS_TIMEOUT_SECONDS", "20"))
FAST_AI_MODE = os.getenv("FAST_AI_MODE", "1").lower() in {"1", "true", "yes", "on"}

# FastAPI app
app = FastAPI(
    title="E-waste Detection API",
    description="AI pipeline for detecting and analyzing e-waste objects",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline: E_WasteDetectionPipeline | None = None


def get_pipeline() -> E_WasteDetectionPipeline:
    """Lazily initialize the heavy YOLO + VLM pipeline on first use."""
    global pipeline
    if pipeline is None:
        pipeline = E_WasteDetectionPipeline(
            yolo_model_path="yolov8n.pt",
            vlm_model_name="Salesforce/blip2-opt-2.7b"
        )
    return pipeline


def build_timeout_fallback(
    active_pipeline: E_WasteDetectionPipeline,
    image_bytes: bytes,
    image_name: str,
) -> PipelineResult:
    """Return a quick whole-image fallback if the full pipeline times out."""
    quick_detection = active_pipeline.yolo_detector.detect_single(image_bytes, image_name)
    quick_label = quick_detection.detected_device if quick_detection.detected_device != "unknown" else "electronic device"
    quick_analysis = active_pipeline.vlm_analyzer._fallback_analysis(image_bytes)

    fallback_object = DetectedObject(
        yolo_label=quick_label,
        yolo_confidence=quick_detection.confidence,
        vlm_object=quick_analysis.object_name,
        condition=quick_analysis.condition,
        suggestion=(
            f"{quick_analysis.suggestion} "
            "Full AI pipeline timed out, so this result uses the fast fallback analyzer."
        ).strip(),
        eco_score=quick_analysis.eco_score,
        box=(0, 0, 1, 1),
    )

    return PipelineResult(
        status="success",
        image_name=image_name,
        detected_objects=[fallback_object],
        error_message="Full AI pipeline timed out; returned fast fallback analysis.",
    )


def build_fast_analysis(
    active_pipeline: E_WasteDetectionPipeline,
    image_bytes: bytes,
    image_name: str,
) -> PipelineResult:
    """Return a fast whole-image analysis without running the heavy detection pipeline."""
    quick_detection = active_pipeline.yolo_detector.detect_single(image_bytes, image_name)
    quick_label = quick_detection.detected_device if quick_detection.detected_device != "unknown" else "electronic device"
    quick_analysis = active_pipeline.vlm_analyzer._fallback_analysis(image_bytes)

    return PipelineResult(
        status="success",
        image_name=image_name,
        detected_objects=[
            DetectedObject(
                yolo_label=quick_label,
                yolo_confidence=quick_detection.confidence,
                vlm_object=quick_analysis.object_name,
                condition=quick_analysis.condition,
                suggestion=quick_analysis.suggestion,
                eco_score=quick_analysis.eco_score,
                box=(0, 0, 1, 1),
            )
        ],
        error_message="Fast AI mode used for responsive analysis.",
    )


# ============================================================================
# Response Models
# ============================================================================

class ObjectDetectionResponse(BaseModel):
    """Single detected object response"""
    yolo_label: str = Field(..., description="YOLO detected label")
    yolo_confidence: float = Field(..., description="YOLO confidence (0-100)")
    vlm_object: str = Field(..., description="VLM identified object")
    condition: str = Field(..., description="Object condition")
    suggestion: str = Field(..., description="Recycling/repair suggestion")
    eco_score: int = Field(..., description="Recyclability score (0-100)")
    box: tuple = Field(..., description="Bounding box [x1, y1, x2, y2]")


class AnalysisResponse(BaseModel):
    """Single image analysis response"""
    status: str = Field(..., description="success or error")
    image_name: str
    detected_objects: List[ObjectDetectionResponse]
    num_detections: int
    error_message: Optional[str] = None


class BatchAnalysisResponse(BaseModel):
    """Batch analysis response"""
    status: str
    total_images: int
    successful: int
    failed: int
    total_objects_detected: int
    results: List[AnalysisResponse]


class TrainingResponse(BaseModel):
    """YOLO training response"""
    status: str
    message: str
    best_model_path: Optional[str] = None
    metrics: Optional[dict] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    pipeline_loaded: bool
    yolo_ready: bool
    vlm_ready: bool


# ============================================================================
# Health & Utility Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and pipeline health"""
    active_pipeline = pipeline
    return {
        "status": "ok",
        "pipeline_loaded": active_pipeline is not None,
        "yolo_ready": active_pipeline.yolo_detector.model is not None if active_pipeline else False,
        "vlm_ready": active_pipeline.vlm_analyzer.model is not None if active_pipeline else False,
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "E-waste Detection API",
        "docs": "/docs",
        "health": "/health"
    }


# ============================================================================
# Analysis Endpoints
# ============================================================================

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_single_image(
    file: UploadFile = File(...),
    conf_threshold: float = Query(0.25, ge=0.0, le=1.0),
):
    """
    Analyze a single image for e-waste objects.

    - **file**: Image file (JPEG, PNG)
    - **conf_threshold**: YOLO confidence threshold (0.0-1.0)

    Returns detected objects with VLM analysis
    """
    try:
        active_pipeline = get_pipeline()
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Read image
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if FAST_AI_MODE:
            result = build_fast_analysis(active_pipeline, content, file.filename or "image.jpg")
        else:
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        active_pipeline.process_single_image,
                        image_bytes=content,
                        image_name=file.filename or "image.jpg",
                        conf_threshold=conf_threshold,
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning("Single-image analysis timed out for %s", file.filename or "image.jpg")
                result = build_timeout_fallback(active_pipeline, content, file.filename or "image.jpg")

        # Convert to response model
        objects_response = [
            ObjectDetectionResponse(**obj.__dict__)
            for obj in result.detected_objects
        ]

        return AnalysisResponse(
            status=result.status,
            image_name=result.image_name,
            detected_objects=objects_response,
            num_detections=result.num_detections,
            error_message=result.error_message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze-batch", response_model=BatchAnalysisResponse)
async def analyze_batch(
    files: List[UploadFile] = File(...),
    conf_threshold: float = Query(0.25, ge=0.0, le=1.0),
):
    """
    Analyze multiple images for e-waste objects.

    - **files**: Multiple image files
    - **conf_threshold**: YOLO confidence threshold

    Returns batch results with individual detections
    """
    try:
        active_pipeline = get_pipeline()
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 images allowed")

        # Read all images
        image_list = []
        for file in files:
            content = await file.read()
            if content:
                image_list.append((content, file.filename or "image.jpg"))

        if not image_list:
            raise HTTPException(status_code=400, detail="No valid images provided")

        # Process batch
        results = []
        successful = 0
        failed = 0

        for content, image_name in image_list:
            if FAST_AI_MODE:
                result = build_fast_analysis(active_pipeline, content, image_name)
            else:
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            active_pipeline.process_single_image,
                            image_bytes=content,
                            image_name=image_name,
                            conf_threshold=conf_threshold,
                        ),
                        timeout=ANALYSIS_TIMEOUT_SECONDS,
                    )
                except TimeoutError:
                    logger.warning("Batch analysis timed out for %s", image_name)
                    result = build_timeout_fallback(active_pipeline, content, image_name)

            results.append(result)
            if result.status == "success":
                successful += 1
            else:
                failed += 1

        batch_result = BatchResult(
            status="success" if failed == 0 else "partial",
            total_images=len(image_list),
            successful=successful,
            failed=failed,
            results=results,
        )

        # Convert to response model
        results_response = [
            AnalysisResponse(
                status=r.status,
                image_name=r.image_name,
                detected_objects=[
                    ObjectDetectionResponse(**obj.__dict__)
                    for obj in r.detected_objects
                ],
                num_detections=r.num_detections,
                error_message=r.error_message,
            )
            for r in batch_result.results
        ]

        return BatchAnalysisResponse(
            status=batch_result.status,
            total_images=batch_result.total_images,
            successful=batch_result.successful,
            failed=batch_result.failed,
            total_objects_detected=batch_result.total_objects_detected,
            results=results_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


# ============================================================================
# Training Endpoints
# ============================================================================

@app.post("/train-yolo", response_model=TrainingResponse)
async def train_yolo(
    data_yaml_path: str = Query(..., description="Path to data.yaml"),
    epochs: int = Query(50, ge=1, le=500),
    imgsz: int = Query(640, ge=320, le=1280),
    batch_size: int = Query(8, ge=1, le=64),
):
    """
    Fine-tune YOLO on custom e-waste dataset.

    - **data_yaml_path**: Path to data.yaml (YOLO format)
    - **epochs**: Number of training epochs
    - **imgsz**: Input image size
    - **batch_size**: Batch size for training

    Expected data.yaml format:
    ```
    path: /path/to/dataset
    train: images/train
    val: images/val
    nc: 6  # number of classes
    names: ['battery', 'pcb', 'wire', 'charger', 'laptop', 'mobile']
    ```
    """
    try:
        active_pipeline = get_pipeline()
        # Validate data.yaml exists
        if not Path(data_yaml_path).exists():
            raise HTTPException(status_code=400, detail=f"data.yaml not found: {data_yaml_path}")

        # Create training config
        config = TrainingConfig(
            data_yaml=data_yaml_path,
            epochs=epochs,
            imgsz=imgsz,
            batch_size=batch_size,
            device=0 if os.environ.get("CUDA_AVAILABLE") else -1,  # GPU if available, else CPU
        )

        # Fine-tune
        logger.info(f"Starting YOLO fine-tuning with config: {config}")
        result = active_pipeline.yolo_detector.fine_tune(config=config)

        if result["status"] == "success":
            return TrainingResponse(
                status="success",
                message="YOLO fine-tuning completed",
                best_model_path=result.get("best_model_path"),
                metrics=result.get("metrics"),
            )
        else:
            return TrainingResponse(
                status="failed",
                message="YOLO fine-tuning failed",
                error=result.get("error"),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@app.get("/validate-yolo", response_model=dict)
async def validate_yolo(data_yaml_path: str = Query(...)):
    """
    Validate YOLO model on dataset.

    - **data_yaml_path**: Path to data.yaml
    """
    try:
        active_pipeline = get_pipeline()
        if not Path(data_yaml_path).exists():
            raise HTTPException(status_code=400, detail=f"data.yaml not found: {data_yaml_path}")

        result = active_pipeline.yolo_detector.validate(data_yaml=data_yaml_path)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@app.post("/load-model")
async def load_model(model_path: str):
    """
    Load a custom YOLO model.

    - **model_path**: Path to .pt file
    """
    try:
        active_pipeline = get_pipeline()
        if not Path(model_path).exists():
            raise HTTPException(status_code=400, detail=f"Model not found: {model_path}")

        active_pipeline.yolo_detector.load_model(model_path)
        return {
            "status": "success",
            "message": f"Model loaded: {model_path}",
            "model_path": model_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model loading failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.get("/stats")
async def get_stats():
    """Get API statistics"""
    active_pipeline = get_pipeline()
    return {
        "status": "operational",
        "yolo_model": active_pipeline.yolo_detector.model_path,
        "vlm_model": active_pipeline.vlm_analyzer.model_name,
        "device": str(active_pipeline.vlm_analyzer.device),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        log_level="info",
    )
