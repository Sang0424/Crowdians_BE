# app/main.py

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.redis import init_redis, close_redis
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 DB/Redis 초기화, 종료 시 정리"""
    await init_db()
    await init_redis()
    yield
    await close_redis()


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
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import DomainError

@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

app.include_router(api_v1_router)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "Crowdians API"}
