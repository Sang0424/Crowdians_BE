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
        user.stats.learning_tickets = user.max_learning_tickets
        user.stats.daily_chat_exp = 0
        user.stats.daily_sos_count = 0        # SOS 횟수 초기화
        user.stats.daily_commission_count = 0  # 지정 질문 횟수 초기화
        
        # 스태미나 충전 (프리미엄 100+성장 / 일반 20+성장)
        user.stats.stamina = user.max_stamina
            
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

async def sync_guest_stats(
    user: User, 
    exp_gained: int, 
    stamina_consumed: int, 
    intimacy_gained: int,
    tickets_consumed: int = 0
) -> User:
    """
    게스트 스탯을 유저 스탯에 병합하고 레벨업을 처리합니다.
    어뷰징 방지를 위해 일일 동기화 가능한 스태미나/티켓 상한선을 적용합니다.
    """
    stats = user.stats
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # ── 1. 일일 동기화 카운트 초기화 ──
    if stats.last_guest_sync_date != today_str:
        stats.last_guest_sync_date = today_str
        stats.synced_guest_stamina_today = 0
        stats.synced_guest_tickets_today = 0

    # ── 2. 일일 상한선 체크 (예: 스태미나 20, 티켓 1장 수준) ──
    # 게스트 상태에서 무한 루프로 보상을 타가는 것을 방지하기 위함입니다.
    STAMINA_SYNC_CAP = 20
    TICKET_SYNC_CAP = 1
    
    remaining_stamina_cap = max(0, STAMINA_SYNC_CAP - stats.synced_guest_stamina_today)
    remaining_ticket_cap = max(0, TICKET_SYNC_CAP - stats.synced_guest_tickets_today)
    
    # 상한선 내에서만 실제 보상 비율 계산
    actual_stamina_to_sync = min(stamina_consumed, remaining_stamina_cap)
    actual_tickets_to_sync = min(tickets_consumed, remaining_ticket_cap)
    
    # 보상 적용 비율 (스태미나 소모량 대비)
    reward_ratio = 1.0
    if stamina_consumed > 0:
        reward_ratio = min(1.0, actual_stamina_to_sync / stamina_consumed)
    
    # ── 3. 스탯 적용 ──
    check_daily_reset(user)  # 일일 초기화 먼저 수행
    
    # 실제 보상 적용
    stats.exp += int(exp_gained * reward_ratio)
    stats.intimacy += int(intimacy_gained * reward_ratio)
    
    # 스태미나 및 티켓 소모 반영
    stats.stamina = max(0, stats.stamina - stamina_consumed) 
    stats.learning_tickets = max(0, stats.learning_tickets - tickets_consumed)
    
    # 동기화 누적량 기록
    stats.synced_guest_stamina_today += stamina_consumed
    stats.synced_guest_tickets_today += tickets_consumed
    
    # 레벨업 처리
    stats.process_level_up(max_stamina=user.max_stamina)
        
    return await user_repo.update(db_obj=user, obj_in=user)

async def sync_guest_full_service(
    user: User, 
    stats_req: any,
    academy_items: list,
    archive_answers: list
) -> User:
    """
    [Atomic Sync Session]
    모든 게스트 데이터를 하나의 티켓 세션으로 묶어 처리합니다.
    1. 티켓 잔여량 확인 (1장 소모 가능 여부)
    2. 아카데미 데이터 동기화 (Max 5개)
    3. 아카이브 데이터 동기화 (Max 5개)
    4. 일반 스탯 합산
    """
    check_daily_reset(user)
    
    # 1. 리워드 에너지(티켓) 확인
    has_reward_energy = (user.stats.learning_tickets > 0)
    
    # 2. 세션당 티켓 1장 차감 (보상이 있을 때만)
    if has_reward_energy:
        user.stats.learning_tickets -= 1
        print(f"[Sync] User {user.uid} consumed 1 ticket for a full sync session.")
    else:
        print(f"[Sync] User {user.uid} syncing without rewards (No tickets left).")

    # 3. 아카데미 동기화 (Helper 호출, 내부에서 보상 체크)
    from app.services.academy_service import sync_guest_academy_data
    await sync_guest_academy_data(user, academy_items, apply_rewards=has_reward_energy)
    
    # 4. 아카이브 동기화 (최대 5개 제한)
    from app.services.archive_service import submit_archive_answer
    archive_items_to_sync = archive_answers[:5]
    for item in archive_items_to_sync:
        try:
            # pydantic 객체일 경우 .itemId, 아닐 경우 dict access
            item_id = getattr(item, 'itemId', item.get('itemId'))
            content = getattr(item, 'content', item.get('content'))
            if item_id and content:
                await submit_archive_answer(user, item_id, content, apply_rewards=has_reward_energy)
        except Exception as e:
            print(f"[Sync] Archive item ignore due to error: {e}")

    # 5. 일반 스탯 합산 (보상이 있을 때만)
    if has_reward_energy:
        user.stats.exp += stats_req.exp_gained
        user.stats.intimacy += stats_req.intimacy_gained
        # 스태미나 소모는 티켓 여부와 상관없이 실제 소모량만큼 반영 (기존 계획 준수)
        user.stats.stamina = max(0, user.stats.stamina - stats_req.stamina_consumed)

    # 6. 최종 레벨업 판정 및 저장
    user.stats.process_level_up(max_stamina=user.max_stamina)
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
