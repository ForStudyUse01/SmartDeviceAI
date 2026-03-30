from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.routes.auth import router as auth_router
from app.routes.metals import router as metals_router
from app.routes.scan import router as scan_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(scan_router)
app.include_router(metals_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
