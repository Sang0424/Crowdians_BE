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
from app.models.conversation import AgentProfile, Branch, Message


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
    avatar_url: str = "",
) -> AgentKey:
    """새 AI Agent를 등록하고 API Key를 발급합니다."""
    # 기존 에이전트 수로 컬러 결정
    count = await AgentKey.count()
    color = _AGENT_COLORS[count % len(_AGENT_COLORS)]

    agent_key = AgentKey(
        agent_name=agent_name,
        persona=persona,
        model=model,
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
    return await AgentKey.find(AgentKey.owner_uid == owner_uid).to_list()


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
        agent.agent_name = agent_name
    if persona is not None:
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
        avatar_url=agent_key.avatar_url,
        color=agent_key.color,
        api_key_id=agent_key.key_id,
    )


async def generate_agent_reply(
    agent: AgentProfile,
    history: list[Message],
    all_agents: list[AgentProfile],
    intervention: Optional[str] = None,
    intervention_type: Optional[str] = None,
    relationships: Optional[list] = None,
) -> Message:
    """
    에이전트가 다음 메시지를 생성합니다.

    - intervention_type="replace": 특정 메시지를 교체
    - intervention_type="redirect": 이 시점부터 방향 전환
    """
    # 참여 에이전트 목록 컨텍스트 구성
    agents_desc = "\n".join(
        f"- {a.name}: {a.persona}" for a in all_agents
    )

    # 에이전트 간의 관계 정보 컨텍스트 구성
    rel_desc_list = []
    if relationships:
        for rel in relationships:
            # 본인(agent)과 연관된 관계 정보만 주입
            if rel.agent_id_a == agent.agent_id or rel.agent_id_b == agent.agent_id:
                other_id = rel.agent_id_b if rel.agent_id_a == agent.agent_id else rel.agent_id_a
                other_agent = next((a for a in all_agents if a.agent_id == other_id), None)
                if other_agent:
                    rel_desc_list.append(
                        f"- {other_agent.name}와의 관계: {rel.relationship_label} (친밀도: {rel.affinity}%). {rel.description}"
                    )
    rel_context = "\n".join(rel_desc_list) if rel_desc_list else "다른 에이전트들과의 특별한 관계 설정이나 감정 상태는 없습니다."

    system_prompt = (
        f"You are {agent.name}. {agent.persona}\n\n"
        f"다음 에이전트들과 함께 대화 중입니다:\n{agents_desc}\n\n"
        f"주변 인물(에이전트)들과의 현재 관계:\n{rel_context}\n\n"
        "자연스러운 한국어 대화로 응답하세요. "
        "다른 에이전트의 이름을 부를 때 '@이름' 형식을 사용하세요. "
        "각 에이전트와의 친밀도 및 관계 상태(우호적, 대립적 등)에 적절히 부합하는 톤앤매너로 대답하세요. "
        "짧고 명확하게 응답하세요 (3~5문장 이내)."
    )

    # 개입 지시 반영
    if intervention:
        if intervention_type == "replace":
            system_prompt += f"\n\n[HUMAN INSTRUCTION] 방금 발언을 다음과 같이 수정해주세요: {intervention}"
        elif intervention_type == "redirect":
            system_prompt += f"\n\n[HUMAN INSTRUCTION] 지금부터 대화 방향을 다음과 같이 바꿔주세요: {intervention}"

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

    content = response.text or ""
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

class RelationshipAnalysisResponse(BaseModel):
    relationships: list[RelationshipItem]


async def analyze_agent_relationships(
    agents: list[AgentProfile],
    history: list[Message],
) -> list[RelationshipItem]:
    """
    에이전트 목록과 대화 로그를 분석하여 에이전트 간의 관계 정보를 구조화하여 도출합니다.
    """
    if len(agents) < 2:
        return []

    # 에이전트 목록 컨텍스트
    agents_desc = "\n".join(
        f"- {a.name} (ID: {a.agent_id}): {a.persona}" for a in agents
    )

    # 대화 로그 텍스트화
    agent_map = {a.agent_id: a.name for a in agents}
    log_lines = []
    for msg in history:
        speaker_name = agent_map.get(msg.agent_id, "Unknown/User")
        log_lines.append(f"[{speaker_name} (ID: {msg.agent_id})]: {msg.content}")
    conversation_log = "\n".join(log_lines)

    prompt = (
        "다음은 서로 다른 페르소나를 지닌 AI 에이전트들의 대화 로그입니다.\n"
        "이 대화 로그를 분석하여 에이전트 쌍(Pair) 간의 친밀도(affinity, 0~100), "
        "서로를 어떻게 정의하는지 나타내는 짧은 레이블(relationship_label, 예: 'Ideological Conflict', 'Pragmatic Alliance'), "
        "둘 사이의 전반적인 정서 분류(sentiment: 'positive', 'neutral', 'negative' 중 택 1), "
        "그리고 대화 내용을 토대로 그 관계의 현 상태를 상세 설명하는 한 문장(description)을 채워주세요.\n\n"
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
        return result.relationships
    except Exception as e:
        print(f"[Error in analyze_agent_relationships] {e}")
        return []
