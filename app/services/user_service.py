# app/services/user_service.py

from datetime import datetime, timezone
from app.models.user import User
from app.db.repository.user_repository import UserRepository

user_repo = UserRepository()

def check_daily_reset(user: User) -> bool:
    """유저의 일일 초기화 상태를 확인하고 필요시 초기화합니다."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    is_reset = False
    
    if user.stats.last_daily_reset != today_str:
        user.stats.learning_tickets = user.stats.max_learning_tickets
        user.stats.daily_chat_exp = 0
        user.stats.stamina = user.stats.max_stamina
        user.stats.last_daily_reset = today_str
        is_reset = True
        
    return is_reset

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
    
    # 일일 초기화 체크 (스태미너가 20으로 리셋될 수 있으므로 먼저 수행)
    check_daily_reset(user)
    
    stats.exp += exp_gained
    stats.intimacy += intimacy_gained
    stats.stamina = max(0, stats.stamina - stamina_consumed)
    
    # 레벨업 처리
    stats.process_level_up()
        
    return await user_repo.update(db_obj=user, obj_in=user)

async def get_user_activities(
    uid: str,
    tab: str,  # answered | asked | saved | voted
    page: int,
    limit: int,
) -> dict:
    """
    유저 활동 목록을 탭별로 조회합니다.
    """
    from app.services import archive_service
    from app.db.repository.user_repository import UserRepository
    
    skip = (page - 1) * limit
    posts = []
    total = 0
    
    if tab == "all":
        # 모든 활동을 가져와서 합친 후 정렬 (최신순)
        asked, _ = await archive_service.get_user_asked_posts(uid, skip=0, limit=100)
        answered, _ = await archive_service.get_user_answered_posts(uid, skip=0, limit=100)
        voted, _ = await archive_service.get_user_voted_answers(uid, skip=0, limit=100)
        
        user_repo = UserRepository()
        user = await user_repo.get_by_uid(uid)
        saved = []
        if user:
            saved, _ = await archive_service.get_user_bookmarked_posts(user, skip=0, limit=100)
            
        all_items = asked + answered + voted + saved
        # sort by createdAt descending
        all_items.sort(key=lambda x: x.get("createdAt"), reverse=True)
        total = len(all_items)
        posts = all_items[skip:skip+limit]
    elif tab == "asked":
        posts, total = await archive_service.get_user_asked_posts(uid, skip=skip, limit=limit)
    elif tab == "answered":
        posts, total = await archive_service.get_user_answered_posts(uid, skip=skip, limit=limit)
    elif tab == "saved":
        user_repo = UserRepository()
        user = await user_repo.get_by_uid(uid)
        if user:
            posts, total = await archive_service.get_user_bookmarked_posts(user, skip=skip, limit=limit)
    elif tab == "voted":
        posts, total = await archive_service.get_user_voted_answers(uid, skip=skip, limit=limit)
        
    return {
        "tab": tab,
        "items": posts,
        "total": total,
        "page": page,
        "limit": limit,
    }
