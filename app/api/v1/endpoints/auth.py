from datetime import datetime, timezone
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
    VerifyAdultRequest,
    OnboardRequest,
)
from app.api.v1.utils import user_to_response
from app.services.auth_service import (
    verify_internal_api_key,
    get_or_create_user,
    generate_access_token,
    generate_refresh_token,
    save_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
)

router = APIRouter()


def _is_under_14(b_date: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if b_date.tzinfo is None:
        b_date = b_date.replace(tzinfo=timezone.utc)
    age = now.year - b_date.year
    if (now.month, now.day) < (b_date.month, b_date.day):
        age -= 1
    return age < 14


# ══════════════════════════════════════
# POST /auth/login — 소셜 로그인 / 회원가입
# ══════════════════════════════════════

@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="소셜 로그인 / 자동 회원가입",
    description="서버 간 신뢰 기반으로 로그인을 처리합니다.",
)
async def login(
    request: LoginRequest,
    x_internal_api_key: str | None = Header(None),
):
    # ── NextAuth → 백엔드 (서버 간 신뢰) ──
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

    # ── 공통: 유저 조회/생성 → 자체 토큰 발급 ──
    if request.birthdate and _is_under_14(request.birthdate):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ERROR_UNDER_AGE_LIMIT",
        )

    user, is_new_user = await get_or_create_user(
        uid=uid,
        email=email,
        nickname=nickname,
        provider=request.provider,
        birthdate=request.birthdate,
    )

    if user.birthdate and _is_under_14(user.birthdate):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ERROR_UNDER_AGE_LIMIT",
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
    description="현재 로그인한 유저의 닉네임을 변경합니다. (2~12자)",
)
async def update_nickname(
    request: NicknameRequest,
    current_user: CurrentUser,
):
    # 예약된 닉네임 사용 금지
    if request.nickname in ("크라우디언", "크라우디언즈", "Crowdians", "crowdians", "Crowdian", "crowdian"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="사용할 수 없는 닉네임입니다.",
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


# # ══════════════════════════════════════
# # GET /users/me — 내 정보 조회
# # ══════════════════════════════════════

# @router.get(
#     "/users/me",
#     response_model=UserResponse,
#     summary="내 정보 조회",
#     description="현재 로그인한 유저의 전체 정보를 반환합니다.",
# )
# async def get_me(
#     current_user: CurrentUser,
# ):
#     return user_to_response(current_user)


# ══════════════════════════════════════
# POST /auth/verify-adult — 성인 인증 API
# ══════════════════════════════════════

@router.post(
    "/auth/verify-adult",
    response_model=UserResponse,
    summary="성인 인증",
    description="다날/Stripe 연동 결과를 시뮬레이션하여 성인 인증을 처리합니다.",
)
async def verify_adult(
    request: VerifyAdultRequest,
    current_user: CurrentUser,
):
    # provider에 따라 다날/Stripe 연동 결과 시뮬레이션
    # auth_token이 'fail', 'invalid', 'error'인 경우 실패 처리
    if not request.auth_token or request.auth_token.lower() in ("fail", "invalid", "error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="성인 인증에 실패했습니다. 유효하지 않은 인증 토큰입니다.",
        )

    # 성공 시 유저 성인 상태 갱신
    current_user.is_adult = True
    current_user.adult_verified_at = datetime.now(timezone.utc)
    await current_user.save()

    return user_to_response(current_user)


# ══════════════════════════════════════
# PATCH /users/me/onboard — 온보딩 정보 갱신
# ══════════════════════════════════════

@router.patch(
    "/users/me/onboard",
    response_model=UserResponse,
    summary="온보딩 정보 갱신",
    description="닉네임, 생년월일, NSFW 필터를 설정하며 만 14세 미만인 경우 차단합니다.",
)
async def onboard_user(
    request: OnboardRequest,
    current_user: CurrentUser,
):
    # 만 나이 검증
    if _is_under_14(request.birthdate):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ERROR_UNDER_AGE_LIMIT",
        )

    # 닉네임 유효성 검사 (입력된 경우)
    if request.nickname:
        reserved = {"크라우디언", "크라우디언즈", "Crowdians", "crowdians", "Crowdian", "crowdian"}
        if request.nickname in reserved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="사용할 수 없는 닉네임입니다.",
            )
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

    current_user.birthdate = request.birthdate
    if request.nsfw_filter is not None:
        current_user.nsfw_filter = request.nsfw_filter

    current_user.stats.isOnboardingDone = True

    await current_user.save()
    return user_to_response(current_user)
