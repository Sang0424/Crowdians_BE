# app/schemas/user.py

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


# ── 공통 스탯/캐릭터 (auth.py에서 재사용) ──

class UserStatsResponse(BaseModel):
    level: int
    exp: int
    maxExp: int
    gold: int
    stamina: int
    maxStamina: int
    trust: int
    intelligence: int
    courage: int
    intimacy: int
    dailyChatExp: int
    dailyPetCount: int
    dailySosCount: int
    dailyCommissionCount: int
    isOnboardingDone: bool
    hasCompletedFirstCommission: bool
    learningTickets: int
    maxLearningTickets: int
    title: Optional[str] = ""

class GuestStatsSyncRequest(BaseModel):
    exp_gained: int
    stamina_consumed: int
    intimacy_gained: int
    tickets_consumed: int = 0


class EquippedPartsResponse(BaseModel):
    head: str
    hand: str
    body: str
    effect: str


class CharacterResponse(BaseModel):
    type: str
    equippedParts: EquippedPartsResponse
    unlockedParts: list[str]


# ── 유저 프로필 (공개) ──

class UserProfileResponse(BaseModel):
    """다른 유저의 공개 프로필 (민감 정보 제외)"""
    uid: str
    nickname: str
    stats: UserStatsResponse
    character: CharacterResponse
    createdAt: datetime
    title: Optional[str] = ""
    subscriptionPlan: str
    subscriptionExpiresAt: Optional[datetime] = None


# ── 유저 활동 탭 ──

class ArchiveActivityItem(BaseModel):
    id: str
    type: str  # 'quest' | 'post' | 'comment'
    title: str
    status: str  # 'active' | 'complete' | 'failed' | 'open' | 'answered'
    category: str
    isSOS: bool
    createdAt: datetime
    content: str
    tags: list[str]
    summary: str

class UserActivitiesResponse(BaseModel):
    tab: str
    items: List[ArchiveActivityItem]
    total: int
    page: int
    limit: int


# ── 회원탈퇴 ──

class DeleteAccountResponse(BaseModel):
    success: bool
    message: str


# ── 캐릭터 설정 ──

class CharacterTypeUpdateRequest(BaseModel):
    """캐릭터 타입 업데이트 요청"""
    type: str

class NicknameUpdateRequest(BaseModel):
    """닉네임 업데이트 요청"""
    nickname: str


class TitleUpdateRequest(BaseModel):
    """칭호 업데이트 요청"""
    title: str
