# app/models/user.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


class UserStats(BaseModel):
    """유저 스탯 (임베디드 모델)"""
    level: int = 1
    exp: int = 0
    max_exp: int = 100
    gold: int = 0                 # Gold (G)
    stamina: int = 20
    max_stamina: int = 20
    trust: int = 1000             # 신뢰도 (기본 1000)
    intelligence: int = 0         # 지능
    courage: int = 0              # 용기
    intimacy: int = 0             # 친밀도
    daily_chat_exp: int = 0       # 오늘 채팅 EXP (일일 상한 50)


class CharacterInfo(BaseModel):
    """캐릭터 정보 (임베디드 모델)"""
    id: str = "char_default"
    name: str = "알"
    image: Optional[str] = None


class User(Document):
    """유저 Document (MongoDB collection: users)"""
    uid: str                                    # Firebase UID (unique)
    email: Optional[str] = None
    nickname: str = "크라우디언"
    provider: str = "google"                    # google / kakao / naver

    stats: UserStats = Field(default_factory=UserStats)
    character: CharacterInfo = Field(default_factory=CharacterInfo)

    role: str = "user"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"                          # MongoDB collection name
        use_state_management = True
