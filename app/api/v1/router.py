# app/api/v1/router.py

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, chat, academy, archive, adventure, mailbox, reports, rankings, quests, subscriptions

api_v1_router = APIRouter(prefix="/api/v1")

# ── 인증 ──
api_v1_router.include_router(auth.router, tags=["Auth"])

# ── 유저 ──
api_v1_router.include_router(users.router, tags=["Users"])

# ── 의뢰 (Quests) ──
api_v1_router.include_router(quests.router, prefix="/quests", tags=["Quests"])

# ── 채팅 ──
api_v1_router.include_router(chat.router, tags=["Chat"])

# ── 아카데미 ──
api_v1_router.include_router(academy.router, tags=["Academy"])

# ── 지식 도서관 (Archive) ──
api_v1_router.include_router(archive.router, tags=["Archive"])

# ── 모험 (Adventure) ──
api_v1_router.include_router(adventure.router, tags=["Adventure"])

# ── 기타 기능 (Misc) ──
api_v1_router.include_router(mailbox.router, tags=["Mailbox"])
api_v1_router.include_router(reports.router, tags=["Reports"])
api_v1_router.include_router(rankings.router, tags=["Rankings"])
api_v1_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
