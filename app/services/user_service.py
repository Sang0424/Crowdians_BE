# app/services/user_service.py

from typing import Optional
from app.models.user import User


async def get_user_by_uid(uid: str) -> Optional[User]:
    """UID로 유저 조회"""
    return await User.find_one(User.uid == uid)


async def delete_user(user: User) -> None:
    """유저를 DB에서 삭제합니다."""
    await user.delete()


async def get_scrapped_conversations(uid: str) -> list[str]:
    """유저가 스크랩한 branch_id 목록 반환"""
    user = await User.find_one(User.uid == uid)
    if not user:
        return []
    return user.scrapped_branches


async def get_liked_branches(uid: str) -> list[str]:
    """유저가 좋아요한 branch_id 목록 반환"""
    user = await User.find_one(User.uid == uid)
    if not user:
        return []
    return user.liked_branches
