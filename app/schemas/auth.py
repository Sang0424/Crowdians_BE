# app/schemas/auth.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Embedded sub-schemas (camelCase for frontend compatibility) ──

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
    learningTickets: int
    maxLearningTickets: int


class EquippedPartsResponse(BaseModel):
    head: str
    hand: str
    body: str
    effect: str


class CharacterResponse(BaseModel):
    type: str
    equippedParts: EquippedPartsResponse
    unlockedParts: list[str]


class UserResponse(BaseModel):
    uid: str
    email: Optional[str] = None
    nickname: str
    stats: UserStatsResponse
    character: CharacterResponse
    createdAt: datetime
    lastLoginAt: datetime


# ── Login ──

class LoginRequest(BaseModel):
    # ── Firebase 토큰 검증 흐름 (모바일 등) ──
    idToken: Optional[str] = Field(None, description="Firebase ID Token (모바일 클라이언트용)")

    # ── NextAuth 서버 간 신뢰 흐름 ──
    providerAccountId: Optional[str] = Field(None, description="소셜 프로바이더 유저 ID")
    email: Optional[str] = Field(None, description="유저 이메일")
    name: Optional[str] = Field(None, description="유저 이름")

    # ── 공통 ──
    provider: str = Field(
        ...,
        pattern=r"^(google|discord|twitter)$",
        description="소셜 로그인 제공자",
    )


class LoginResponse(BaseModel):
    isNewUser: bool
    user: UserResponse
    accessToken: str
    refreshToken: str


# ── Nickname ──

class NicknameRequest(BaseModel):
    nickname: str = Field(
        ...,
        min_length=2,
        max_length=12,
        description="닉네임 (2~12자)",
    )


class NicknameResponse(BaseModel):
    success: bool
    nickname: str


# ── Token Refresh ──

class RefreshRequest(BaseModel):
    refreshToken: str = Field(..., description="리프레시 토큰")


class RefreshResponse(BaseModel):
    accessToken: str
