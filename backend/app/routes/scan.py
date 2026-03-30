from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.database import get_database
from app.core.security import get_current_token
from app.ml.predict import predict_scan
from app.models.scan import ScanInDB, ScanResponse
from app.schemas.scan import RecentScansResponse

router = APIRouter(tags=["scan"])


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
