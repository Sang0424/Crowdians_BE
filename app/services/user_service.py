# app/services/user_service.py

from app.models.user import User
from app.db.repository.user_repository import UserRepository

user_repo = UserRepository()

async def get_user_by_uid(uid: str) -> User | None:
    """UID로 유저 조회"""
    return await user_repo.get_by_uid(uid)

async def delete_user(user: User) -> None:
    """
    유저를 DB에서 삭제합니다.
    Firebase Auth 계정 삭제는 클라이언트에서 처리하거나
    별도 Firebase Admin SDK 호출로 삭제할 수 있습니다.
    """
    await user_repo.delete(db_obj=user)

async def sync_guest_stats(user: User, exp_gained: int, stamina_consumed: int, intimacy_gained: int) -> User:
    """
    게스트 스탯을 유저 스탯에 병합하고 레벨업을 처리합니다.
    """
    stats = user.stats
    stats.exp += exp_gained
    stats.intimacy += intimacy_gained
    stats.stamina = max(0, stats.stamina - stamina_consumed)
    
    # 레벨업 처리
    max_exp = stats.max_exp
    while stats.exp >= max_exp:
        stats.exp -= max_exp
        stats.level += 1
        stats.stamina = stats.max_stamina
        max_exp = stats.max_exp
        
    return await user_repo.update(db_obj=user, obj_in=user)

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
