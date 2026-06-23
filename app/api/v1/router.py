# app/api/v1/router.py

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, reports, dpo, billing
from app.api.v1.endpoints import channels, agents, ws, feed

api_v1_router = APIRouter(prefix="/api/v1")

# ── 인증 ──
api_v1_router.include_router(auth.router, tags=["Auth"])

# ── 유저 ──
api_v1_router.include_router(users.router, tags=["Users"])

# ── 대화 & 분기 ──
api_v1_router.include_router(channels.router)

# ── AI Agent ──
api_v1_router.include_router(agents.router)

# ── 신고 ──
api_v1_router.include_router(reports.router, tags=["Reports"])

# ── WebSocket ──
api_v1_router.include_router(ws.router)

# ── Feed (Marketplace) ──
api_v1_router.include_router(feed.router)

# ── DPO 데이터셋 ──
api_v1_router.include_router(dpo.router)

# ── 결제 및 젬 ──
api_v1_router.include_router(billing.router, tags=["Billing"])


