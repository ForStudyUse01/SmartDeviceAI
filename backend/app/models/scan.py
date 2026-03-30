from datetime import UTC, datetime

from pydantic import BaseModel


class StatusFlags(BaseModel):
    repairable: bool
    hazardous: bool
    recyclable: bool


class ScanResponse(BaseModel):
    id: str
    component: str
    metals: dict[str, str]
    value: int
    risk: str
    deviceHealth: int
    resaleValue: int
    co2Saved: float
    lifecycleCompletion: int
    status: StatusFlags
    createdAt: datetime


class ScanInDB(BaseModel):
    user_id: str
    filename: str
    component: str
    metals: dict[str, str]
    value: int
    risk: str
    device_health: int
    resale_value: int
    co2_saved: float
    lifecycle_completion: int
    status: StatusFlags
    created_at: datetime

    @classmethod
    def from_prediction(cls, user_id: str, filename: str, prediction: dict) -> "ScanInDB":
        return cls(
            user_id=user_id,
            filename=filename,
            component=prediction["component"],
            metals=prediction["metals"],
            value=prediction["value"],
            risk=prediction["risk"],
            device_health=prediction["deviceHealth"],
            resale_value=prediction["resaleValue"],
            co2_saved=prediction["co2Saved"],
            lifecycle_completion=prediction["lifecycleCompletion"],
            status=StatusFlags(**prediction["status"]),
            created_at=datetime.now(UTC),
        )
