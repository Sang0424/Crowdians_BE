# app/schemas/auth.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UserStatsResponse(BaseModel):
    level: int
    exp: int
    branches_created: int
    likes_received: int
    conversations_joined: int
    isOnboardingDone: bool = False


class UserResponse(BaseModel):
    uid: str
    email: Optional[str] = None
    nickname: str
    user_type: str
    avatar_url: str
    stats: UserStatsResponse
    createdAt: datetime
    lastLoginAt: datetime
    birthdate: Optional[datetime] = None
    isAdult: bool = False
    adultVerifiedAt: Optional[datetime] = None
    nsfwFilter: bool = True


class LoginRequest(BaseModel):
    idToken: Optional[str] = Field(None)
    providerAccountId: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    name: Optional[str] = Field(None)
    provider: str = Field(..., pattern=r"^(google|discord|twitter)$")
    birthdate: Optional[datetime] = Field(None)


class LoginResponse(BaseModel):
    isNewUser: bool
    user: UserResponse
    accessToken: str
    refreshToken: str


class NicknameRequest(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=12)


class NicknameResponse(BaseModel):
    success: bool
    nickname: str


class RefreshRequest(BaseModel):
    refreshToken: str


class RefreshResponse(BaseModel):
    accessToken: str


class VerifyAdultRequest(BaseModel):
    provider: str = Field(..., pattern=r"^(KCB|DANAL|TOSS|STRIPE|CREDIT_CARD)$")
    auth_token: str


class OnboardRequest(BaseModel):
    nickname: Optional[str] = Field(None, min_length=2, max_length=12)
    birthdate: datetime
    nsfw_filter: Optional[bool] = Field(None)
