# app/api/v1/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    NicknameRequest,
    NicknameResponse,
    RefreshRequest,
    RefreshResponse,
    UserResponse,
)
from app.api.v1.utils import user_to_response
from app.services.auth_service import (
    verify_firebase_token,
    get_or_create_user,
    generate_access_token,
    generate_refresh_token,
    save_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
)

router = APIRouter()




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

    # 3. 토큰 생성 및 Redis 저장
    access_token = generate_access_token(uid)
    refresh_token = generate_refresh_token(uid)
    await save_refresh_token(uid, refresh_token)

    return LoginResponse(
        isNewUser=is_new_user,
        user=user_to_response(user),
        accessToken=access_token,
        refreshToken=refresh_token,
    )


# ══════════════════════════════════════
# POST /auth/refresh — AccessToken 재발급
# ══════════════════════════════════════

@router.post(
    "/auth/refresh",
    response_model=RefreshResponse,
    summary="토큰 갱신",
    description="RefreshToken으로 새로운 AccessToken을 발급합니다.",
)
async def refresh_token(request: RefreshRequest):
    try:
        uid = await verify_refresh_token(request.refreshToken)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    new_access_token = generate_access_token(uid)

    return RefreshResponse(accessToken=new_access_token)


# ══════════════════════════════════════
# POST /auth/logout — 로그아웃
# ══════════════════════════════════════

@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    description="RefreshToken을 무효화합니다. 이후 해당 토큰으로 재발급이 불가합니다.",
)
async def logout(
    request: RefreshRequest,
    current_user: User = Depends(get_current_user),
):
    await revoke_refresh_token(request.refreshToken)


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
    return user_to_response(current_user)
