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


class UserResponse(BaseModel):
    uid: str
    email: Optional[str] = None
    nickname: str
    user_type: str
    avatar_url: str
    stats: UserStatsResponse
    createdAt: datetime
    lastLoginAt: datetime


class LoginRequest(BaseModel):
    idToken: Optional[str] = Field(None)
    providerAccountId: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    name: Optional[str] = Field(None)
    provider: str = Field(..., pattern=r"^(google|discord|twitter)$")


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
