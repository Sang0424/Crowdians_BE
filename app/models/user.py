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
    learning_tickets: int = 3      # 오늘 남은 아카데미 티켓 수
    ticket_recharges_today: int = 0 # 오늘 광고로 충전한 티켓 수 (최대 5)
    daily_pet_count: int = 0       # 오늘 쓰다듬은 횟수 (일일 상한 30)
    last_pet_date: Optional[datetime] = None # 마지막으로 쓰다듬은 날짜
    last_daily_reset: str = ""    # 마지막 일일 초기화 날짜 (YYYY-MM-DD 포맷)
    is_onboarding_done: bool = False # 온보딩 완료 여부
    title: str = ""               # 칭호 (텍스트 기반 보상)

    @property
    def max_exp(self) -> int:
        """레벨업에 필요한 경험치: 50 * level^1.6"""
        return round(50 * (self.level ** 1.6))

    @property
    def max_stamina(self) -> int:
        """최대 스태미너: 20 + (친밀도 // 50)"""
        return 20 + (self.intimacy // 50)

    @property
    def max_learning_tickets(self) -> int:
        """최대 아카데미 티켓 수: 3 + (신뢰도 // 200)"""
        return 3 + (self.trust - 1000) // 200

    def process_level_up(self):
        """경험치가 넘칠 경우 레벨업을 반복 처리(while)하고 스태미나를 완충합니다."""
        while self.exp >= self.max_exp:
            self.exp -= self.max_exp
            self.level += 1
            self.stamina = self.max_stamina


class EquippedParts(BaseModel):
    """장착된 파츠 정보"""
    head: str = ""
    hand: str = ""
    body: str = ""
    effect: str = ""


class CharacterInfo(BaseModel):
    """캐릭터 정보 (임베디드 모델)"""
    type: str = "unknown"
    equipped_parts: EquippedParts = Field(default_factory=EquippedParts)
    unlocked_parts: list[str] = Field(default_factory=list)


class User(Document):
    """유저 Document (MongoDB collection: users)"""
    uid: str                                    # Firebase UID (unique)
    email: Optional[str] = None
    nickname: str 
    provider: str                     # google / discord / twitter
    bookmarked_posts: list[str] = []
    title: str | None = None

    stats: UserStats = Field(default_factory=UserStats)
    character: CharacterInfo = Field(default_factory=CharacterInfo)

    # ── Donation & Titles ──
    donation_tier: str = "none"                # "none" | "pioneer" | "explorer" | "guardian"
    total_donated: float = 0.0                 # 누적 후원 금액 (USD 기준)
    available_titles: list[str] = []           # 해금된 칭호 목록 (pioneer, explorer, guardian)

    role: str = "user"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"                          # MongoDB collection name
        use_state_management = True
