from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.security import CurrentUser
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
    verify_internal_api_key,
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
    description="Firebase ID Token 또는 서버 간 신뢰 기반으로 로그인을 처리합니다.",
)
async def login(
    request: LoginRequest,
    x_internal_api_key: str | None = Header(None),
):
    # ── 흐름 A: NextAuth → 백엔드 (서버 간 신뢰) ──
    if x_internal_api_key is not None:
        try:
            verify_internal_api_key(x_internal_api_key)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )

        if not request.providerAccountId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="providerAccountId가 필요합니다.",
            )

        # provider:providerAccountId 조합으로 고유한 uid 생성
        uid = f"{request.provider}:{request.providerAccountId}"
        email = request.email
        nickname = None

    # ── 흐름 B: 모바일 등 (Firebase ID Token 검증) ──
    else:
        if not request.idToken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="idToken이 필요합니다.",
            )

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
        email = decoded.get("email")
        nickname = None

    # ── 공통: 유저 조회/생성 → 자체 토큰 발급 ──
    user, is_new_user = await get_or_create_user(
        uid=uid,
        email=email,
        nickname=nickname,
        provider=request.provider,
    )

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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
):
    # 예약된 닉네임 사용 금지
    if request.nickname == "크라우디언":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'크라우디언'은 설정할 수 없는 닉네임입니다.",
        )

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
    current_user: CurrentUser,
):
    return user_to_response(current_user)
