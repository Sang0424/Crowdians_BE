# app/services/auth_service.py

from datetime import datetime, timezone

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

from app.core.security import create_access_token
from app.models.user import User, UserStats, CharacterInfo


# ── Firebase Admin SDK 초기화 ──
# GOOGLE_APPLICATION_CREDENTIALS 환경변수가 설정되어 있으면 자동으로 읽힘
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)


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
