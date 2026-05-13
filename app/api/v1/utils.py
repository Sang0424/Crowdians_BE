# app/api/v1/utils.py
# 여러 엔드포인트에서 공통으로 사용하는 변환 유틸리티

from app.models.user import User
from app.schemas.auth import UserResponse, UserStatsResponse


def user_to_response(user: User) -> UserResponse:
    """DB User 모델을 auth 응답 스키마로 변환"""
    return UserResponse(
        uid=user.uid,
        email=user.email,
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
        createdAt=user.created_at,
        lastLoginAt=user.last_login_at,
    )
