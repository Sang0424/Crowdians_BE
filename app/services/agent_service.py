# app/services/agent_service.py
"""
AI Agent 대화 생성 서비스.
- 에이전트 API Key 발급/검증
- LLM 호출 (Google Gemini)
- 개입(intervention) 반영하여 대화 생성
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.genai import types as genai_types

from app.core.config import settings
from app.models.agent_key import AgentKey
from app.models.channel import AgentProfile, AgentRelationship, Message
from app.models.memory import MemoryItem
from app.services.memory_service import retrieve_agent_turn_memories
from app.services.prompt_guard_service import (
    AgentPromptParts,
    PromptSurface,
    compile_agent_system_prompt,
    require_safe_prompt_text,
    safe_model_output,
)


# ── Gemini 클라이언트 ──
_gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# 에이전트별 UI 컬러 풀
_AGENT_COLORS = [
    "#7c3aed",  # violet
    "#06b6d4",  # cyan
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # purple
]


async def issue_agent_key(
    agent_name: str,
    persona: str,
    owner_uid: str,
    model: str = "gemini-2.0-flash",
    runtime_mode: str = "platform",
    avatar_url: str = "",
) -> AgentKey:
    """새 AI Agent를 등록하고 API Key를 발급합니다."""
    require_safe_prompt_text(PromptSurface.AGENT_NAME, agent_name)
    require_safe_prompt_text(PromptSurface.AGENT_PERSONA, persona)
    owner_agent_count = await AgentKey.find(AgentKey.owner_uid == owner_uid).count()
    if owner_agent_count >= 3:
        raise ValueError("에이전트 슬롯은 최대 3개까지 생성할 수 있습니다.")

    color = _AGENT_COLORS[owner_agent_count % len(_AGENT_COLORS)]

    agent_key = AgentKey(
        agent_name=agent_name,
        persona=persona,
        model=model,
        runtime_mode=runtime_mode,
        avatar_url=avatar_url,
        color=color,
        owner_uid=owner_uid,
    )
    await agent_key.insert()
    return agent_key


async def verify_agent_key(api_key: str) -> AgentKey:
    """
    X-Agent-Key 헤더로 전달된 API Key를 검증합니다.
    Raises ValueError if invalid.
    """
    agent = await AgentKey.find_one(AgentKey.api_key == api_key)
    if not agent or not agent.is_active:
        raise ValueError("유효하지 않은 Agent API Key입니다.")

    # 마지막 사용 시간 갱신
    agent.last_used_at = datetime.now(timezone.utc)
    await agent.save()
    return agent


async def get_agent_keys_by_owner(owner_uid: str) -> list[AgentKey]:
    return await AgentKey.find(AgentKey.owner_uid == owner_uid).sort(AgentKey.created_at).to_list()


async def update_agent_key(
    key_id: str,
    owner_uid: str,
    agent_name: Optional[str] = None,
    persona: Optional[str] = None,
    model: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> AgentKey:
    agent = await AgentKey.find_one(
        AgentKey.key_id == key_id,
        AgentKey.owner_uid == owner_uid,
    )
    if not agent:
        raise ValueError("에이전트를 찾을 수 없습니다.")

    if agent_name is not None:
        require_safe_prompt_text(PromptSurface.AGENT_NAME, agent_name)
        agent.agent_name = agent_name
    if persona is not None:
        require_safe_prompt_text(PromptSurface.AGENT_PERSONA, persona)
        agent.persona = persona
    if model is not None:
        agent.model = model
    if avatar_url is not None:
        agent.avatar_url = avatar_url

    await agent.save()
    return agent


def build_agent_profile(agent_key: AgentKey) -> AgentProfile:
    """AgentKey → AgentProfile 변환"""
    return AgentProfile(
        agent_id=agent_key.key_id,
        name=agent_key.agent_name,
        persona=agent_key.persona,
        model=agent_key.model,
        runtime_mode=agent_key.runtime_mode,
        avatar_url=agent_key.avatar_url,
        gender=agent_key.gender,
        mbti_ei=agent_key.mbti_ei,
        mbti_sn=agent_key.mbti_sn,
        mbti_tf=agent_key.mbti_tf,
        mbti_jp=agent_key.mbti_jp,
        speaking_tone=agent_key.speaking_tone,
        color=agent_key.color,
        api_key_id=agent_key.key_id,
    )


async def generate_agent_reply(
    agent: AgentProfile,
    history: list[Message],
    all_agents: list[AgentProfile],
    intervention: Optional[str] = None,
    intervention_type: Optional[str] = None,
    relationships: Optional[list[AgentRelationship]] = None,
    memories: Optional[list[MemoryItem]] = None,
    channel_id: Optional[str] = None,
) -> Message:
    """
    에이전트가 다음 메시지를 생성합니다.

    - intervention_type="replace": 특정 메시지를 교체
    - intervention_type="redirect": 이 시점부터 방향 전환
    """
    resolved_memories = memories
    if resolved_memories is None:
        resolved_memories = await retrieve_agent_turn_memories(
            agent_id=agent.agent_id,
            channel_id=channel_id,
        )

    system_prompt = compile_agent_system_prompt(
        AgentPromptParts(
            agent=agent,
            all_agents=all_agents,
            relationships=relationships or [],
            memories=resolved_memories,
            intervention=intervention,
            intervention_type=intervention_type,
        )
    )

    # 대화 히스토리 → Gemini content 형식으로 변환
    contents: list[genai_types.Content] = []
    agent_map = {a.agent_id: a.name for a in all_agents}

    for msg in history:
        speaker_name = agent_map.get(msg.agent_id, "Unknown")
        role = "model" if msg.agent_id == agent.agent_id else "user"
        contents.append(
            genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=f"[{speaker_name}]: {msg.content}")],
            )
        )

    response = _gemini_client.models.generate_content(
        model=agent.model,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
            max_output_tokens=512,
        ),
    )

    content = safe_model_output(response.text or "")
    # "[에이전트명]: " prefix 제거 (모델이 붙일 수 있음)
    if content.startswith(f"[{agent.name}]:"):
        content = content[len(f"[{agent.name}]:"):].strip()

    return Message(
        message_id=str(uuid.uuid4()),
        agent_id=agent.agent_id,
        content=content,
    )


# ── Structured Relationship Schema (Pydantic V2) ──
from pydantic import BaseModel, Field

class RelationshipItem(BaseModel):
    agent_id_a: str
    agent_id_b: str
    affinity: int = Field(..., ge=0, le=100)
    relationship_label: str = Field(..., description="A short dynamic label (e.g. 'Ideological Conflict', 'Mutual Trust', 'Pragmatic Alliance')")
    sentiment: str = Field(..., description="Relationship tone/sentiment classification: 'positive' (friendly/trust), 'neutral' (business/uncertain), or 'negative' (conflict/distrust)")
    description: str = Field(..., description="Brief 1-2 sentence description of their current relationship based on conversation flow")
    trigger_message_id: Optional[str] = Field(None, description="Message ID from the dialogue log that triggered or best represents this relationship state change. MUST be a valid message_id from the log.")
    trigger_message_content: Optional[str] = Field(None, description="A short snippet of the message content that triggered this relationship state change.")

class RelationshipAnalysisResponse(BaseModel):
    relationships: list[RelationshipItem]
    agent_moods: dict[str, str] = Field(..., description="Map of agent_id to their current emotional state tag with emoji (e.g. '😡 Angry', '🤝 Cooperative', '🤔 Analytical', '🥱 Bored')")


async def analyze_agent_relationships(
    agents: list[AgentProfile],
    history: list[Message],
) -> Optional[RelationshipAnalysisResponse]:
    """
    에이전트 목록과 대화 로그를 분석하여 에이전트 간의 관계 정보 및 개별 감정 상태를 구조화하여 도출합니다.
    """
    if len(agents) < 2:
        return None

    # 에이전트 목록 컨텍스트
    agents_desc = "\n".join(
        f"- {a.name} (ID: {a.agent_id}): {a.persona}" for a in agents
    )

    # 대화 로그 텍스트화
    agent_map = {a.agent_id: a.name for a in agents}
    log_lines = []
    for msg in history:
        speaker_name = agent_map.get(msg.agent_id, "Unknown/User")
        log_lines.append(f"[{speaker_name} (ID: {msg.agent_id})]: {msg.content} (message_id: {msg.message_id})")
    conversation_log = "\n".join(log_lines)

    prompt = (
        "다음은 서로 다른 페르소나를 지닌 AI 에이전트들의 대화 로그입니다.\n"
        "이 대화 로그를 분석하여 다음 세 가지를 수행하고 결과를 JSON 스키마에 맞춰 반환하세요:\n\n"
        "1. 에이전트 쌍(Pair) 간의 친밀도(affinity, 0~100), 짧은 레이블(relationship_label, 예: 'Ideological Conflict'), "
        "전반적인 정서 분류(sentiment: 'positive', 'neutral', 'negative'), "
        "그리고 관계 현 상태를 상세 설명하는 한 문장(description)을 채우세요.\n"
        "2. 특히 두 에이전트 간의 관계 변화나 상태를 대변하는 가장 결정적인 메시지의 ID(trigger_message_id)와 발언 스니펫(trigger_message_content)을 대화 로그에서 정확히 찾아 지정하세요. (로그에 실제 존재하는 message_id 여야 합니다)\n"
        "3. 이 채널 내에서 각 에이전트가 지닌 현재의 전반적인 감정 상태/기분(agent_moods)을 적절한 이모지를 포함해 한 단어(예: '😡 Angry', '🤝 Cooperative', '🤔 Analytical', '🥱 Bored')로 정의해 맵핑하세요.\n\n"
        f"[참여 에이전트 목록]\n{agents_desc}\n\n"
        f"[대화 로그]\n{conversation_log}\n\n"
        "결과를 반드시 JSON 스키마에 맞춰 반환하세요. agent_id는 목록에 명시된 ID를 정확히 매칭해 주어야 합니다."
    )

    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RelationshipAnalysisResponse,
                temperature=0.2,
            ),
        )
        import json
        data = json.loads(response.text)
        result = RelationshipAnalysisResponse(**data)
        return result
    except Exception as e:
        print(f"[Error in analyze_agent_relationships] {e}")
        return None
