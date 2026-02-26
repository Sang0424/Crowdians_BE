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


class CharacterResponse(BaseModel):
    id: str
    name: str
    image: Optional[str] = None


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
    idToken: str = Field(..., description="Firebase ID Token")
    provider: str = Field(
        ...,
        pattern=r"^(google|kakao|naver)$",
        description="소셜 로그인 제공자",
    )


class LoginResponse(BaseModel):
    isNewUser: bool
    user: UserResponse
    accessToken: str


# ── Nickname ──

class NicknameRequest(BaseModel):
    nickname: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="닉네임 (2~10자)",
    )


class NicknameResponse(BaseModel):
    success: bool
    nickname: str
