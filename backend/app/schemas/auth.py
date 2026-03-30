from pydantic import BaseModel

from app.models.user import UserPublic


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
