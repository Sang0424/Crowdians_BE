# app/api/v1/router.py

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, chat, academy

api_v1_router = APIRouter(prefix="/api/v1")

# ── 인증 ──
api_v1_router.include_router(auth.router, tags=["Auth"])

# ── 유저 ──
api_v1_router.include_router(users.router, tags=["Users"])

# ── 채팅 ──
api_v1_router.include_router(chat.router, tags=["Chat"])

# ── 아카데미 ──
api_v1_router.include_router(academy.router, tags=["Academy"])
