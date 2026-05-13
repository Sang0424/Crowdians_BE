# app/services/auth_service.py

from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from jose import JWTError, jwt

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserStats


# ── Firebase Admin SDK 초기화 ──
if not firebase_admin._apps:
    cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
    firebase_admin.initialize_app(cred)

_RT_PREFIX = "refresh_token:"


def verify_internal_api_key(api_key: str | None) -> None:
    if not api_key:
        raise ValueError("Internal API Key가 누락되었습니다.")
    if api_key != settings.INTERNAL_API_KEY:
        raise ValueError("유효하지 않은 Internal API Key입니다.")


async def verify_firebase_token(id_token: str) -> dict:
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as e:
        raise ValueError(f"Firebase 토큰 검증 실패: {str(e)}")


async def get_or_create_user(
    uid: str,
    email: str | None,
    nickname: str | None,
    provider: str,
) -> tuple[User, bool]:
    user = await User.find_one(User.uid == uid)

    if user is not None:
        user.last_login_at = datetime.now(timezone.utc)
        await user.save()
        return user, False

    new_user = User(
        uid=uid,
        email=email,
        nickname=nickname or "크라우디언",
        provider=provider,
        stats=UserStats(),
        role="user",
    )
    await new_user.insert()
    return new_user, True


def generate_access_token(uid: str) -> str:
    return create_access_token(data={"sub": uid})


def generate_refresh_token(uid: str) -> str:
    return create_refresh_token(data={"sub": uid})


async def save_refresh_token(uid: str, refresh_token: str) -> None:
    redis = get_redis()
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    await redis.setex(
        name=f"{_RT_PREFIX}{refresh_token}",
        time=ttl_seconds,
        value=uid,
    )


async def verify_refresh_token(refresh_token: str) -> str:
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise ValueError("리프레시 토큰이 아닙니다.")
        uid: str | None = payload.get("sub")
        if not uid:
            raise ValueError("토큰에 UID가 없습니다.")
    except JWTError as e:
        raise ValueError(f"토큰 검증 실패: {str(e)}")

    redis = get_redis()
    stored_uid = await redis.get(f"{_RT_PREFIX}{refresh_token}")
    if stored_uid is None:
        raise ValueError("만료되거나 로그아웃된 토큰입니다.")
    if stored_uid != uid:
        raise ValueError("토큰의 UID가 일치하지 않습니다.")

    return uid


async def revoke_refresh_token(refresh_token: str) -> None:
    redis = get_redis()
    await redis.delete(f"{_RT_PREFIX}{refresh_token}")
