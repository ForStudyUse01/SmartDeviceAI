from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.security import create_access_token, get_current_token, hash_password, verify_password
from app.models.user import UserCreate, UserInDB, UserPublic
from app.schemas.auth import AuthResponse

router = APIRouter(tags=["auth"])


def serialize_user(document: dict) -> UserPublic:
    return UserPublic(id=str(document["_id"]), email=document["email"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate, database=Depends(get_database)) -> AuthResponse:
    user = UserInDB.from_create(payload.email, hash_password(payload.password))
    try:
        result = await database.users.insert_one(user.model_dump())
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists") from exc

    public_user = UserPublic(id=str(result.inserted_id), email=payload.email)
    access_token = create_access_token(public_user.id, public_user.email)
    return AuthResponse(access_token=access_token, user=public_user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: UserCreate, database=Depends(get_database)) -> AuthResponse:
    user = await database.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    public_user = serialize_user(user)
    access_token = create_access_token(public_user.id, public_user.email)
    return AuthResponse(access_token=access_token, user=public_user)


@router.get("/me", response_model=UserPublic)
async def me(token_payload: dict = Depends(get_current_token), database=Depends(get_database)) -> UserPublic:
    user = await database.users.find_one({"_id": ObjectId(token_payload["sub"])})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return serialize_user(user)
