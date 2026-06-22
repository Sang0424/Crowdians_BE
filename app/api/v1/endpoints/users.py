# app/api/v1/endpoints/users.py

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.security import CurrentUser
from app.models.user import User, AvatarImages
from app.services.user_service import get_user_by_uid, delete_user


router = APIRouter()


# ── Schemas (간소화) ──

class UserStatsResponse(BaseModel):
    branches_created: int
    likes_received: int
    conversations_joined: int
    isOnboardingDone: bool = False


class UserProfileResponse(BaseModel):
    uid: str
    nickname: str
    stats: UserStatsResponse
    scrapped_branches: list[str]
    liked_branches: list[str]
    created_at: datetime
    birthdate: Optional[datetime] = None
    is_adult: bool = False
    adult_verified_at: Optional[datetime] = None
    nsfw_filter: bool = True
    data_opt_in: bool = False
    mbti: Optional[str] = None
    avatar_url: Optional[str] = None


class NicknameUpdateRequest(BaseModel):
    nickname: str


class AvatarUrlUpdateRequest(BaseModel):
    avatar_url: Optional[str] = None


class DeleteAccountResponse(BaseModel):
    success: bool
    message: str



class AvatarImagesIn(BaseModel):
    default: str
    happy: str
    sad: str
    angry: str
    surprised: str
    blushed: str


class UserOnboardRequest(BaseModel):
    nickname: str
    birthdate: datetime
    data_opt_in: bool = False


class AvatarCreateRequest(BaseModel):
    mbti: str
    personality_tags: list[str]
    avatar_images: AvatarImagesIn


class AvatarCreateResponse(BaseModel):
    user: UserProfileResponse


def _user_to_profile(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        uid=user.uid,
        nickname=user.nickname,
        stats=UserStatsResponse(
            branches_created=user.stats.branches_created,
            likes_received=user.stats.likes_received,
            conversations_joined=user.stats.conversations_joined,
            isOnboardingDone=user.stats.isOnboardingDone,
        ),
        scrapped_branches=user.scrapped_branches,
        liked_branches=user.liked_branches,
        created_at=user.created_at,
        birthdate=user.birthdate,
        is_adult=user.is_adult,
        adult_verified_at=user.adult_verified_at,
        nsfw_filter=user.nsfw_filter,
        data_opt_in=user.data_opt_in,
        mbti=user.mbti,
        avatar_url=user.avatar_url,
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


@router.post("/users/onboard", response_model=UserProfileResponse, summary="회원가입 필수 온보딩 정보 입력")
async def onboard_user(request: UserOnboardRequest, current_user: CurrentUser):
    # 나이 제한 검사 (만 14세 미만 가입 제한)
    today = datetime.now()
    age = today.year - request.birthdate.year - ((today.month, today.day) < (request.birthdate.month, request.birthdate.day))
    if age < 14:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="만 14세 미만의 아동은 가입이 제한됩니다. (ERROR_UNDER_AGE_LIMIT)"
        )
    
    # 닉네임 중복 및 예약어 검사
    reserved = {"크라우디언", "크라우디언즈", "Crowdians", "crowdians"}
    if request.nickname in reserved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="사용할 수 없는 닉네임입니다.")
    existing = await User.find_one(User.nickname == request.nickname, User.uid != current_user.uid)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 닉네임입니다.")
        
    current_user.nickname = request.nickname
    current_user.birthdate = request.birthdate
    current_user.data_opt_in = request.data_opt_in
    current_user.stats.isOnboardingDone = True
    await current_user.save()
    return _user_to_profile(current_user)


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


@router.patch("/users/me/avatar-url", response_model=UserProfileResponse, summary="프로필 이미지 변경")
async def update_avatar_url(request: AvatarUrlUpdateRequest, current_user: CurrentUser):
    current_user.avatar_url = request.avatar_url
    await current_user.save()
    return _user_to_profile(current_user)


@router.delete("/users/me", response_model=DeleteAccountResponse, summary="회원탈퇴")
async def delete_account(current_user: CurrentUser):
    await delete_user(current_user)
    return DeleteAccountResponse(success=True, message="계정이 삭제되었습니다.")


@router.post("/users/avatar", response_model=AvatarCreateResponse, summary="아바타 생성")
async def create_user_avatar(request: AvatarCreateRequest, current_user: CurrentUser):
    current_user.mbti = request.mbti
    current_user.personality_tags = request.personality_tags
    current_user.avatar_images = AvatarImages(
        default=request.avatar_images.default,
        happy=request.avatar_images.happy,
        sad=request.avatar_images.sad,
        angry=request.avatar_images.angry,
        surprised=request.avatar_images.surprised,
        blushed=request.avatar_images.blushed
    )
    
    await current_user.save()
    
    return AvatarCreateResponse(
        user=_user_to_profile(current_user)
    )
