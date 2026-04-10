import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.redis import init_redis, close_redis
from app.core.exceptions import DomainError
from app.core.i18n import get_text
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

@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    # Accept-Language 헤더에서 로케일 추출 (예: ko-KR -> ko)
    accept_lang = request.headers.get("accept-language", "ko")
    locale = accept_lang.split(",")[0].split("-")[0].lower()
    if locale not in ["ko", "en", "ja"]:
        locale = "ko"
    
    # 1. 예외 code에 해당하는 번역 키가 있는지 확인
    error_key = f"error.{exc.code.lower()}"
    localized_message = get_text(error_key, locale=locale, **exc.params)
    
    # 2. 번역 키를 못 찾은 경우 (key 자체가 반환됨) exc.message 사용
    if localized_message == error_key:
        localized_message = exc.message

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": localized_message,
            "code": exc.code
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    logging.error(f"Unhandled error: {exc}")
    logging.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)}
    )

app.include_router(api_v1_router)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "Crowdians API"}
