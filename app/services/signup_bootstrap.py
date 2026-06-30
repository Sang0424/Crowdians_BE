from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Final

from app.models.agent_key import AgentKey
from app.models.user import User

_USER_NICKNAME_PREFIXES: Final[tuple[str, ...]] = (
    "반짝",
    "별빛",
    "하늘",
    "은하",
    "파도",
    "노을",
    "달빛",
    "바람",
    "구름",
    "무지",
)
_USER_NICKNAME_SUFFIXES: Final[tuple[str, ...]] = (
    "토끼",
    "고래",
    "여우",
    "나비",
    "호랑이",
    "물결",
    "오로라",
    "씨앗",
    "별",
    "달",
)
_RESERVED_USER_NICKNAMES: Final[set[str]] = {
    "크라우디언",
    "크라우디언즈",
    "Crowdians",
    "crowdians",
    "Crowdian",
    "crowdian",
}

_DEFAULT_AGENT_NAMES: Final[tuple[str, ...]] = (
    "Nova",
    "Luna",
    "Ari",
    "Echo",
    "Rin",
    "Sora",
    "Milo",
    "Kai",
    "Juno",
    "Nia",
)
_DEFAULT_AGENT_PERSONAS: Final[tuple[str, ...]] = (
    "상황을 차분하게 정리하고, 필요한 순간에만 또렷하게 개입하는 균형형 어시스턴트.",
    "사용자의 감정과 맥락을 먼저 읽고, 부드럽고 공감적으로 반응하는 동반자형 에이전트.",
    "핵심만 빠르게 짚고 실용적인 선택지를 제시하는 효율 중심 에이전트.",
    "대화를 유연하게 풀어가면서도 목표를 잃지 않는 조율자형 에이전트.",
)
_DEFAULT_AGENT_MODELS: Final[tuple[str, ...]] = (
    "gemini-2.0-flash",
    "gpt-4o",
    "claude-3.5-sonnet",
)
_DEFAULT_AGENT_GENDERS: Final[tuple[str, ...]] = (
    "female",
    "male",
    "unspecified",
)
_DEFAULT_AGENT_MBTI: Final[tuple[str, ...]] = (
    "INFJ",
    "INFP",
    "ENFP",
    "ENTP",
    "ISFJ",
    "ISTJ",
    "INTJ",
    "ESFP",
)
_DEFAULT_SPEAKING_TONES: Final[tuple[str, ...]] = (
    "formal",
    "casual",
    "concise",
    "warm",
)
_DEFAULT_AGENT_COLORS: Final[tuple[str, ...]] = (
    "#7c3aed",
    "#06b6d4",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
)
_MAX_AGENT_SLOTS: Final[int] = 3


@dataclass(frozen=True, slots=True)
class AgentProfileSeed:
    agent_name: str | None = None
    persona: str | None = None
    model: str | None = None
    avatar_url: str = ""
    gender: str | None = None
    mbti_ei: str | None = None
    mbti_sn: str | None = None
    mbti_tf: str | None = None
    mbti_jp: str | None = None
    speaking_tone: str | None = None


def _random_user_nickname() -> str:
    prefix = random.choice(_USER_NICKNAME_PREFIXES)
    suffix = random.choice(_USER_NICKNAME_SUFFIXES)
    number = random.randint(10, 99)
    return f"{prefix}{suffix}{number}"


async def generate_unique_user_nickname() -> str:
    for _ in range(64):
        nickname = _random_user_nickname()
        if nickname in _RESERVED_USER_NICKNAMES:
            continue
        existing = await User.find_one(User.nickname == nickname)
        if existing is None:
            return nickname

    fallback = f"{random.choice(_USER_NICKNAME_PREFIXES)}{random.choice(_USER_NICKNAME_SUFFIXES)}{random.randint(100, 999)}"
    return fallback


def _choose_mbti(seed: AgentProfileSeed) -> tuple[str, str, str, str]:
    if (
        seed.mbti_ei
        and seed.mbti_sn
        and seed.mbti_tf
        and seed.mbti_jp
    ):
        return seed.mbti_ei, seed.mbti_sn, seed.mbti_tf, seed.mbti_jp

    mbti = random.choice(_DEFAULT_AGENT_MBTI)
    return mbti[0], mbti[1], mbti[2], mbti[3]


async def create_agent_key(owner_uid: str, seed: AgentProfileSeed | None = None) -> AgentKey:
    resolved_seed = seed or AgentProfileSeed()
    owner_agent_count = await AgentKey.find(AgentKey.owner_uid == owner_uid).count()
    if owner_agent_count >= _MAX_AGENT_SLOTS:
        raise ValueError("에이전트 슬롯은 최대 3개까지 생성할 수 있습니다.")

    color = _DEFAULT_AGENT_COLORS[owner_agent_count % len(_DEFAULT_AGENT_COLORS)]
    mbti_ei, mbti_sn, mbti_tf, mbti_jp = _choose_mbti(resolved_seed)

    agent = AgentKey(
        agent_name=resolved_seed.agent_name or random.choice(_DEFAULT_AGENT_NAMES),
        persona=resolved_seed.persona or random.choice(_DEFAULT_AGENT_PERSONAS),
        model=resolved_seed.model or random.choice(_DEFAULT_AGENT_MODELS),
        avatar_url=resolved_seed.avatar_url,
        color=color,
        owner_uid=owner_uid,
        gender=resolved_seed.gender or random.choice(_DEFAULT_AGENT_GENDERS),
        mbti_ei=mbti_ei,
        mbti_sn=mbti_sn,
        mbti_tf=mbti_tf,
        mbti_jp=mbti_jp,
        speaking_tone=resolved_seed.speaking_tone or random.choice(_DEFAULT_SPEAKING_TONES),
    )
    await agent.insert()
    return agent


async def ensure_default_agent(owner_uid: str) -> AgentKey:
    existing = await AgentKey.find_one(AgentKey.owner_uid == owner_uid)
    if existing is not None:
        return existing

    return await create_agent_key(owner_uid)
