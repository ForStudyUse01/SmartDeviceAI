from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_token

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


def _rule_based_reply(message: str) -> str:
    text = message.lower().strip()
    if "battery" in text:
        return "For battery issues: reduce screen brightness, disable background sync for heavy apps, and check battery health in settings."
    if "overheat" in text or "heating" in text or "hot" in text:
        return "For overheating: remove heavy background apps, avoid charging during gaming, and keep ventilation clear."
    if "slow" in text or "lag" in text or "performance" in text:
        return "For slow performance: clear storage (15%+ free), uninstall unused apps, restart weekly, and update OS."
    if "crash" in text or "app" in text:
        return "For app crashes: clear app cache, update the app, check permissions, and reinstall if the issue persists."
    if "screen" in text or "display" in text:
        return "For screen problems: inspect for cracks, test touch response, reduce pressure points, and back up data before repair."
    return "I can help with battery, overheating, slow performance, app crashes, and screen issues. Share your symptom for targeted steps."


@router.post("/chat", response_model=ChatResponse)
async def chat_assistant(payload: ChatRequest, token_payload: dict = Depends(get_current_token)) -> ChatResponse:
    _ = token_payload
    return ChatResponse(reply=_rule_based_reply(payload.message))
