# app/api/v1/endpoints/users.py

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.security import CurrentUser
from app.models.user import User
from app.services.user_service import get_user_by_uid, delete_user


router = APIRouter()


# ── Schemas (간소화) ──

class UserStatsResponse(BaseModel):
    level: int
    exp: int
    branches_created: int
    likes_received: int
    conversations_joined: int


class UserProfileResponse(BaseModel):
    uid: str
    nickname: str
    user_type: str
    avatar_url: str
    stats: UserStatsResponse
    scrapped_branches: list[str]
    liked_branches: list[str]
    created_at: datetime


class NicknameUpdateRequest(BaseModel):
    nickname: str


class DeleteAccountResponse(BaseModel):
    success: bool
    message: str


def _user_to_profile(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        uid=user.uid,
        nickname=user.nickname,
        user_type=user.user_type,
        avatar_url=user.avatar_url,
        stats=UserStatsResponse(
            level=user.stats.level,
            exp=user.stats.exp,
            branches_created=user.stats.branches_created,
            likes_received=user.stats.likes_received,
            conversations_joined=user.stats.conversations_joined,
        ),
        scrapped_branches=user.scrapped_branches,
        liked_branches=user.liked_branches,
        created_at=user.created_at,
    )


# ── Endpoints ──

@router.get("/users/me", response_model=UserProfileResponse, summary="내 프로필 조회")
async def get_my_profile(current_user: CurrentUser):
    return _user_to_profile(current_user)


@router.get("/users/{uid}", response_model=UserProfileResponse, summary="유저 프로필 조회")
async def get_user_profile(uid: str):
    user = await get_user_by_uid(uid)
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return _user_to_profile(user)


@router.patch("/users/me/nickname", response_model=UserProfileResponse, summary="닉네임 변경")
async def update_nickname(request: NicknameUpdateRequest, current_user: CurrentUser):
    reserved = {"크라우디언", "크라우디언즈", "Crowdians", "crowdians"}
    if request.nickname in reserved:
        raise HTTPException(status_code=400, detail="사용할 수 없는 닉네임입니다.")
    existing = await User.find_one(User.nickname == request.nickname, User.uid != current_user.uid)
    if existing:
        raise HTTPException(status_code=409, detail="이미 사용 중인 닉네임입니다.")
    current_user.nickname = request.nickname
    await current_user.save()
    return _user_to_profile(current_user)


@router.delete("/users/me", response_model=DeleteAccountResponse, summary="회원탈퇴")
async def delete_account(current_user: CurrentUser):
    await delete_user(current_user)
    return DeleteAccountResponse(success=True, message="계정이 삭제되었습니다.")
