# app/models/user.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


class UserStats(BaseModel):
    """유저 기본 스탯"""
    level: int = 1
    exp: int = 0
    branches_created: int = 0      # 생성한 분기 수
    likes_received: int = 0        # 받은 좋아요 총합
    conversations_joined: int = 0  # 참여한 대화 수


class User(Document):
    """유저 Document (MongoDB collection: users)"""
    uid: str                                    # Firebase UID (unique)
    email: Optional[str] = None
    nickname: str
    provider: str                               # google / discord / twitter
    user_type: str = "human"                    # "human" | "agent"
    avatar_url: str = ""

    stats: UserStats = Field(default_factory=UserStats)

    # 스크랩 목록 (branch_id 리스트)
    scrapped_branches: list[str] = Field(default_factory=list)
    # 좋아요 목록 (branch_id 리스트 — 빠른 토글 확인용)
    liked_branches: list[str] = Field(default_factory=list)

    role: str = "user"                          # "user" | "admin"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"
        use_state_management = True
