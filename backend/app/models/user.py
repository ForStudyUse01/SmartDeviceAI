from datetime import UTC, datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr


class UserInDB(BaseModel):
    email: EmailStr
    hashed_password: str
    created_at: datetime

    @classmethod
    def from_create(cls, email: str, hashed_password: str) -> "UserInDB":
        return cls(email=email, hashed_password=hashed_password, created_at=datetime.now(UTC))
