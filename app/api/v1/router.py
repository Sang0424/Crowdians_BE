# app/api/v1/router.py

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, reports
from app.api.v1.endpoints import conversations, agents, ws, feed

api_v1_router = APIRouter(prefix="/api/v1")

# ── 인증 ──
api_v1_router.include_router(auth.router, tags=["Auth"])

# ── 유저 ──
api_v1_router.include_router(users.router, tags=["Users"])

# ── 대화 & 분기 ──
api_v1_router.include_router(conversations.router)

# ── AI Agent ──
api_v1_router.include_router(agents.router)

# ── 신고 ──
api_v1_router.include_router(reports.router, tags=["Reports"])

# ── WebSocket ──
api_v1_router.include_router(ws.router)

# ── Feed (Marketplace) ──
api_v1_router.include_router(feed.router)
