# app/api/v1/endpoints/users.py

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import CurrentUser, CurrentUser
from app.models.user import User
from app.schemas.user import (
    UserProfileResponse,
    UserStatsResponse,
    CharacterResponse,
    EquippedPartsResponse,
    UserActivitiesResponse,
    DeleteAccountResponse,
    GuestStatsSyncRequest,
    CharacterTypeUpdateRequest,
)
from app.services.user_service import (
    get_user_by_uid,
    delete_user,
    get_user_activities,
    sync_guest_stats as sync_guest_stats_service,
    check_daily_reset
)

router = APIRouter()


# ── Helper: User → 공개 프로필 ──

def _user_to_profile(user: User) -> UserProfileResponse:
    """DB User를 공개 프로필 응답으로 변환 (email 제외)"""
    return UserProfileResponse(
        uid=user.uid,
        nickname=user.nickname,
        stats=UserStatsResponse(
            level=user.stats.level,
            exp=user.stats.exp,
            maxExp=user.stats.max_exp,
            gold=user.stats.gold,
            stamina=user.stats.stamina,
            maxStamina=user.stats.max_stamina,
            trust=user.stats.trust,
            intelligence=user.stats.intelligence,
            courage=user.stats.courage,
            intimacy=user.stats.intimacy,
            dailyChatExp=user.stats.daily_chat_exp,
            dailyPetCount=user.stats.daily_pet_count,
            isOnboardingDone=user.stats.is_onboarding_done,
            learningTickets=user.stats.learning_tickets,
            maxLearningTickets=user.stats.max_learning_tickets,
        ),
        character=CharacterResponse(
            type=user.character.type,
            equippedParts=EquippedPartsResponse(
                head=user.character.equipped_parts.head,
                hand=user.character.equipped_parts.hand,
                body=user.character.equipped_parts.body,
                effect=user.character.equipped_parts.effect,
            ),
            unlockedParts=user.character.unlocked_parts,
        ),
        createdAt=user.created_at,
        title = user.title
    )

# ══════════════════════════════════════
# GET /users/me — 내 프로필 조회
# ══════════════════════════════════════

@router.get(
    "/users/me",
    response_model=UserProfileResponse,
    summary="내 프로필 조회",
    description="현재 로그인한 유저의 프로필을 조회합니다. (일일 초기화 포함)",
)
async def get_my_profile(
    current_user: CurrentUser,
):
    if check_daily_reset(current_user):
        await current_user.save()
    return _user_to_profile(current_user)

# ══════════════════════════════════════
# GET /users/{uid} — 다른 유저 프로필 조회
# ══════════════════════════════════════

@router.get(
    "/users/{uid}",
    response_model=UserProfileResponse,
    summary="유저 프로필 조회",
    description="특정 유저의 공개 프로필을 조회합니다. (email 등 민감 정보 제외)",
)
async def get_user_profile(uid: str):
    user = await get_user_by_uid(uid)
    if user is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("User")
    return _user_to_profile(user)


# ══════════════════════════════════════
# GET /users/{uid}/activities — 유저 활동 목록
# ══════════════════════════════════════

@router.get(
    "/users/{uid}/activities",
    response_model=UserActivitiesResponse,
    summary="유저 활동 목록 조회",
    description="탭별로 유저의 활동을 조회합니다. tab: answered | asked | saved | voted",
)
async def get_user_activities_endpoint(
    uid: str,
    tab: str = Query(
        default="answered",
        pattern=r"^(answered|asked|saved|voted)$",
        description="활동 탭: answered(내 답변) | asked(내 질문) | saved(저장) | voted(신뢰함)",
    ),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    user = await get_user_by_uid(uid)
    if user is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("User")

    result = await get_user_activities(uid=uid, tab=tab, page=page, limit=limit)
    return UserActivitiesResponse(**result)


# ══════════════════════════════════════
# DELETE /users/me — 회원탈퇴
# ══════════════════════════════════════

@router.delete(
    "/users/me",
    response_model=DeleteAccountResponse,
    summary="회원탈퇴",
    description="현재 로그인한 유저의 계정을 삭제합니다. (복구 불가)",
)
async def delete_account(
    current_user: CurrentUser,
):
    await delete_user(current_user)
    return DeleteAccountResponse(
        success=True,
        message="계정이 삭제되었습니다.",
    )

# ══════════════════════════════════════
# POST /users/me/sync-guest-stats — 게스트 스탯 동기화
# ══════════════════════════════════════

@router.post(
    "/users/me/sync-guest-stats",
    response_model=UserStatsResponse,
    summary="게스트 스탯 동기화",
    description="로그인 시 게스트로서 획득한 스탯을 유저 스탯에 병합합니다.",
)
async def sync_guest_stats(
    request: GuestStatsSyncRequest,
    current_user: CurrentUser,
):
    updated_user = await sync_guest_stats_service(
        current_user,
        request.exp_gained,
        request.stamina_consumed,
        request.intimacy_gained
    )
    
    stats = updated_user.stats
    
    return UserStatsResponse(
        level=stats.level,
        exp=stats.exp,
        maxExp=stats.max_exp,
        gold=stats.gold,
        stamina=stats.stamina,
        maxStamina=stats.max_stamina,
        trust=stats.trust,
        intelligence=stats.intelligence,
        courage=stats.courage,
        intimacy=stats.intimacy,
        dailyChatExp=stats.daily_chat_exp,
        dailyPetCount=stats.daily_pet_count,
        isOnboardingDone=stats.is_onboarding_done,
        learningTickets = stats.learning_tickets,
        maxLearningTickets=stats.max_learning_tickets,
    )


# ══════════════════════════════════════
# POST /users/me/pet — 캐릭터 쓰다듬기
# ══════════════════════════════════════

@router.post(
    "/users/me/pet",
    response_model=UserStatsResponse,
    summary="캐릭터 쓰다듬기",
    description="캐릭터를 쓰다듬어 친밀도를 올리고 일일 횟수를 기록합니다 (최대 30회/일)",
)
async def pet_character(
    current_user: CurrentUser,
):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    # 일일 초기화 체크 (기타 스탯용)
    check_daily_reset(current_user)
    
    # 쓰다듬기 일일 초기화
    if current_user.stats.last_pet_date is None or current_user.stats.last_pet_date.date() != now.date():
        current_user.stats.daily_pet_count = 0
        current_user.stats.last_pet_date = now

    if current_user.stats.daily_pet_count >= 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="오늘은 이미 충분히 쓰다듬었습니다"
        )
    
    current_user.stats.daily_pet_count += 1
    current_user.stats.intimacy += 1
    current_user.stats.last_pet_date = now
    
    await current_user.save()
    
    stats = current_user.stats
    return UserStatsResponse(
        level=stats.level,
        exp=stats.exp,
        maxExp=stats.max_exp,
        gold=stats.gold,
        stamina=stats.stamina,
        maxStamina=stats.max_stamina,
        trust=stats.trust,
        intelligence=stats.intelligence,
        courage=stats.courage,
        intimacy=stats.intimacy,
        dailyChatExp=stats.daily_chat_exp,
        dailyPetCount=stats.daily_pet_count,
        isOnboardingDone=stats.is_onboarding_done,
        learningTickets=stats.learning_tickets,
        maxLearningTickets=stats.max_learning_tickets,
    )


# ══════════════════════════════════════
# PATCH /users/me/character/type — 캐릭터 타입 변경
# ══════════════════════════════════════

@router.patch(
    "/users/me/character/type",
    response_model=UserProfileResponse,
    summary="캐릭터 타입 변경",
    description="현재 유저의 캐릭터 타입을 변경합니다.",
)
async def update_character_type(
    request: CharacterTypeUpdateRequest,
    current_user: CurrentUser,
):
    current_user.character.type = request.type
    await current_user.save()
    
    return _user_to_profile(current_user)
