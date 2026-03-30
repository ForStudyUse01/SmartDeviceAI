from pydantic import BaseModel

from app.models.scan import ScanResponse


class RecentScansResponse(BaseModel):
    scans: list[ScanResponse]
