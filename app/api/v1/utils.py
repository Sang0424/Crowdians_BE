# app/api/v1/utils.py
# 여러 엔드포인트에서 공통으로 사용하는 변환 유틸리티

from app.models.user import User
from app.schemas.auth import UserResponse, UserStatsResponse


def user_to_response(user: User) -> UserResponse:
    """DB User 모델을 auth 응답 스키마로 변환"""
    avatar_url = ""
    if hasattr(user, "avatar_images") and user.avatar_images:
        avatar_url = getattr(user.avatar_images, "default", "")

    return UserResponse(
        uid=user.uid,
        email=user.email,
        nickname=user.nickname,
        user_type="human",
        avatar_url=avatar_url,
        stats=UserStatsResponse(
            level=1,  # level has been removed from UserStats model
            exp=0,    # exp has been removed from UserStats model
            branches_created=user.stats.branches_created,
            likes_received=user.stats.likes_received,
            conversations_joined=user.stats.conversations_joined,
            isOnboardingDone=user.stats.isOnboardingDone,
        ),
        createdAt=user.created_at,
        lastLoginAt=user.last_login_at,
        birthdate=user.birthdate,
        isAdult=user.is_adult,
        adultVerifiedAt=user.adult_verified_at,
        nsfwFilter=user.nsfw_filter,
    )

