# app/api/v1/endpoints/users.py

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import (
    UserProfileResponse,
    UserStatsResponse,
    CharacterResponse,
    EquippedPartsResponse,
    UserActivitiesResponse,
    DeleteAccountResponse,
)
from app.services.user_service import (
    get_user_by_uid,
    delete_user,
    get_user_activities,
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
            gold=user.stats.gold,
            stamina=user.stats.stamina,
            trust=user.stats.trust,
            intelligence=user.stats.intelligence,
            courage=user.stats.courage,
            intimacy=user.stats.intimacy,
            dailyChatExp=user.stats.daily_chat_exp,
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
    )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다.",
        )
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="유저를 찾을 수 없습니다.",
        )

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
    current_user: User = Depends(get_current_user),
):
    await delete_user(current_user)
    return DeleteAccountResponse(
        success=True,
        message="계정이 삭제되었습니다.",
    )
