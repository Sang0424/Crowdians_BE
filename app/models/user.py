# app/models/user.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


class UserStats(BaseModel):
    """유저 스탯 (임베디드 모델)"""
    level: int = 1
    exp: int = 0
    gold: int = 0                 # Gold (G)
    stamina: int = 20
    trust: int = 1000             # 신뢰도 (기본 1000)
    intelligence: int = 0         # 지능
    courage: int = 0              # 용기
    intimacy: int = 0             # 친밀도
    daily_chat_exp: int = 0       # 오늘 채팅 EXP (일일 상한 50)
    academy_tickets: int = 5      # 오늘 남은 아카데미 티켓 수
    ticket_recharges_today: int = 0 # 오늘 광고로 충전한 티켓 수 (최대 5)
    last_daily_reset: str = ""    # 마지막 일일 초기화 날짜 (YYYY-MM-DD 포맷)

    @property
    def max_exp(self) -> int:
        """레벨업에 필요한 경험치: 50 * level^1.6"""
        return int(50 * (self.level ** 1.6))

    @property
    def max_stamina(self) -> int:
        """최대 스태미너 (고정값)"""
        return 20


class EquippedParts(BaseModel):
    """장착된 파츠 정보"""
    head: str = ""
    hand: str = ""
    body: str = ""
    effect: str = ""


class CharacterInfo(BaseModel):
    """캐릭터 정보 (임베디드 모델)"""
    type: str = "pico"
    equipped_parts: EquippedParts = Field(default_factory=EquippedParts)
    unlocked_parts: list[str] = Field(default_factory=list)


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
