# app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 DB 초기화, 종료 시 정리"""
    await init_db()
    yield


app = FastAPI(
    title="Crowdians API",
    description="크라우디언즈 백엔드 REST API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(api_v1_router)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "Crowdians API"}
