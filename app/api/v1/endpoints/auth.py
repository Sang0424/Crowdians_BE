# app/api/v1/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    NicknameRequest,
    NicknameResponse,
    UserResponse,
    UserStatsResponse,
    CharacterResponse,
)
from app.services.auth_service import (
    verify_firebase_token,
    get_or_create_user,
    generate_access_token,
)

router = APIRouter()


# ── Helper: User Document → Response ──

def _user_to_response(user: User) -> UserResponse:
    """DB User 모델을 프론트엔드 호환 Response로 변환"""
    return UserResponse(
        uid=user.uid,
        email=user.email,
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
        ),
        character=CharacterResponse(
            id=user.character.id,
            name=user.character.name,
            image=user.character.image,
        ),
        createdAt=user.created_at,
        lastLoginAt=user.last_login_at,
    )


# ══════════════════════════════════════
# POST /auth/login — 소셜 로그인 / 회원가입
# ══════════════════════════════════════

@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="소셜 로그인 / 자동 회원가입",
    description="Firebase ID Token을 검증하고, 기존 유저면 로그인 / 신규 유저면 자동 회원가입을 처리합니다.",
)
async def login(request: LoginRequest):
    # 1. Firebase ID Token 검증
    try:
        decoded = await verify_firebase_token(request.idToken)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase 토큰에서 UID를 찾을 수 없습니다.",
        )

    # 2. 유저 조회 또는 생성
    user, is_new_user = await get_or_create_user(
        uid=uid,
        email=decoded.get("email"),
        nickname=decoded.get("name"),
        provider=request.provider,
    )

    # 3. JWT 액세스 토큰 생성
    access_token = generate_access_token(uid)

    return LoginResponse(
        isNewUser=is_new_user,
        user=_user_to_response(user),
        accessToken=access_token,
    )


# ══════════════════════════════════════
# PATCH /users/me/nickname — 닉네임 변경
# ══════════════════════════════════════

@router.patch(
    "/users/me/nickname",
    response_model=NicknameResponse,
    summary="닉네임 변경",
    description="현재 로그인한 유저의 닉네임을 변경합니다. (2~10자)",
)
async def update_nickname(
    request: NicknameRequest,
    current_user: User = Depends(get_current_user),
):
    # 닉네임 중복 검사
    existing = await User.find_one(
        User.nickname == request.nickname,
        User.uid != current_user.uid,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 닉네임입니다.",
        )

    current_user.nickname = request.nickname
    await current_user.save()

    return NicknameResponse(
        success=True,
        nickname=current_user.nickname,
    )


# ══════════════════════════════════════
# GET /users/me — 내 정보 조회
# ══════════════════════════════════════

@router.get(
    "/users/me",
    response_model=UserResponse,
    summary="내 정보 조회",
    description="현재 로그인한 유저의 전체 정보를 반환합니다.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return _user_to_response(current_user)
