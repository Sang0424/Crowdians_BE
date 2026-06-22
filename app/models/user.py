# app/models/user.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


class UserStats(BaseModel):
    """유저 활동 스탯"""
    branches_created: int = 0      # 생성한 분기 수
    likes_received: int = 0        # 받은 좋아요 총합
    conversations_joined: int = 0  # 참여한 대화 수
    isOnboardingDone: bool = False # 온보딩 완료 여부


class AvatarImages(BaseModel):
    """유저 아바타의 감정별 프로필 이미지 (Optional)"""
    default: str = ""
    happy: str = ""
    sad: str = ""
    angry: str = ""
    surprised: str = ""
    blushed: str = ""


class User(Document):
    """유저 Document (MongoDB collection: users)"""
    uid: str                                    # Firebase UID (unique)
    email: Optional[str] = None
    nickname: str
    provider: str                               # google / discord / twitter
    avatar_url: Optional[str] = None            # 사용자 프로필 이미지 URL


    # 연령 검증 및 세이프티 가드레일 필드
    birthdate: Optional[datetime] = None        # 생년월일
    is_adult: bool = False                      # 성인인증 완료 여부
    adult_verified_at: Optional[datetime] = None # 성인인증 성공 시간
    nsfw_filter: bool = True                    # 세이프티 필터 (NSFW OFF 여부)
    data_opt_in: bool = False                   # DPO/RLHF 데이터 기여 동의 여부

    stats: UserStats = Field(default_factory=UserStats)

    # 아바타 AI 설정 필드
    mbti: Optional[str] = None                  # 아바타 성향 MBTI 4글자
    personality_tags: list[str] = Field(default_factory=list)
    avatar_images: AvatarImages = Field(default_factory=AvatarImages)

    # 스크랩 목록 (branch_id 리스트)
    scrapped_branches: list[str] = Field(default_factory=list)
    # 좋아요 목록 (branch_id 리스트 — 빠른 토글 확인용)
    liked_branches: list[str] = Field(default_factory=list)

    role: str = "user"                          # "user" | "admin"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def subscription_plan(self) -> str:
        if self.email == "crowdians.crowdy@gmail.com":
            return "premium"
        return "free"

    class Settings:
        name = "users"
        use_state_management = True
