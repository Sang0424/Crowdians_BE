# app/services/auth_service.py

from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserStats, CharacterInfo
from jose import JWTError, jwt


# ── Firebase Admin SDK 초기화 ──
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)

# Redis key prefix
_RT_PREFIX = "refresh_token:"


async def verify_firebase_token(id_token: str) -> dict:
    """
    Firebase ID Token을 검증하고 디코딩된 토큰 정보를 반환합니다.

    Returns:
        dict: uid, email, name, picture 등의 정보가 담긴 딕셔너리
    Raises:
        ValueError: 토큰이 유효하지 않은 경우
    """
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        raise ValueError(f"Firebase 토큰 검증 실패: {str(e)}")


async def get_or_create_user(
    uid: str,
    email: str | None,
    nickname: str | None,
    provider: str,
) -> tuple[User, bool]:
    """
    DB에서 유저를 조회하고, 없으면 새로 생성합니다.

    Returns:
        (user, is_new_user) 튜플
    """
    user = await User.find_one(User.uid == uid)

    if user is not None:
        # ── 기존 유저: 로그인 시간만 갱신 ──
        user.last_login_at = datetime.now(timezone.utc)
        await user.save()
        return user, False

    # ── 신규 유저: 초기 데이터로 생성 ──
    new_user = User(
        uid=uid,
        email=email,
        nickname=nickname or "크라우디언",
        provider=provider,
        stats=UserStats(),           # 기본 스탯 (Level 1, Gold 0, Trust 1000 등)
        character=CharacterInfo(),   # 기본 캐릭터
        role="user",
    )
    await new_user.insert()
    return new_user, True


def generate_access_token(uid: str) -> str:
    """유저 UID를 기반으로 JWT 액세스 토큰을 생성합니다."""
    return create_access_token(data={"sub": uid})


def generate_refresh_token(uid: str) -> str:
    """유저 UID를 기반으로 JWT 리프레시 토큰을 생성합니다."""
    return create_refresh_token(data={"sub": uid})


async def save_refresh_token(uid: str, refresh_token: str) -> None:
    """
    Redis에 RefreshToken을 저장합니다.
    키: refresh_token:{token} / 값: uid / TTL: REFRESH_TOKEN_EXPIRE_DAYS
    """
    redis = get_redis()
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    await redis.setex(
        name=f"{_RT_PREFIX}{refresh_token}",
        time=ttl_seconds,
        value=uid,
    )


async def verify_refresh_token(refresh_token: str) -> str:
    """
    RefreshToken을 검증하고 UID를 반환합니다.

    Returns:
        uid (str)
    Raises:
        ValueError: 토큰이 유효하지 않거나 Redis에 없는 경우
    """
    # 1. JWT 서명/만료 검증
    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise ValueError("리프레시 토큰이 아닙니다.")
        uid: str | None = payload.get("sub")
        if not uid:
            raise ValueError("토큰에 UID가 없습니다.")
    except JWTError as e:
        raise ValueError(f"토큰 검증 실패: {str(e)}")

    # 2. Redis 화이트리스트 확인 (로그아웃 여부 체크)
    redis = get_redis()
    stored_uid = await redis.get(f"{_RT_PREFIX}{refresh_token}")
    if stored_uid is None:
        raise ValueError("만료되거나 로그아웃된 토큰입니다.")
    if stored_uid != uid:
        raise ValueError("토큰의 UID가 일치하지 않습니다.")

    return uid


async def revoke_refresh_token(refresh_token: str) -> None:
    """Redis에서 RefreshToken을 삭제합니다 (로그아웃)."""
    redis = get_redis()
    await redis.delete(f"{_RT_PREFIX}{refresh_token}")
