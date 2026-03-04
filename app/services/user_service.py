# app/services/user_service.py

from app.models.user import User


async def get_user_by_uid(uid: str) -> User | None:
    """UID로 유저 조회"""
    return await User.find_one(User.uid == uid)


async def delete_user(user: User) -> None:
    """
    유저를 DB에서 삭제합니다.
    Firebase Auth 계정 삭제는 클라이언트에서 처리하거나
    별도 Firebase Admin SDK 호출로 삭제할 수 있습니다.
    """
    await user.delete()


async def get_user_activities(
    uid: str,
    tab: str,  # answered | asked | saved | voted
    page: int,
    limit: int,
) -> dict:
    """
    유저 활동 목록을 탭별로 조회합니다.
    현재는 빈 목록을 반환하며, 각 기능(아카데미, 지식 도서관) 구현 후 채워집니다.
    """
    return {
        "tab": tab,
        "items": [],
        "total": 0,
        "page": page,
        "limit": limit,
    }
