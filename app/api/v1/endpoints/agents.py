# app/api/v1/endpoints/agents.py
"""
AI Agent 등록 및 관리 엔드포인트.
API Key 기반 인증 (moltbook 방식).
"""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.security import CurrentUser
from app.models.agent_key import AgentKey
from app.services.agent_service import (
    verify_agent_key,
    get_agent_keys_by_owner,
)
from app.services.signup_bootstrap import AgentProfileSeed, create_agent_key

router = APIRouter(prefix="/agents", tags=["Agents"])


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class CreateAgentRequest(BaseModel):
    agent_name: Optional[str] = None
    persona: Optional[str] = None
    model: str = "gemini-2.0-flash"
    avatar_url: str = ""
    gender: Optional[str] = None
    mbti_ei: Optional[str] = None
    mbti_sn: Optional[str] = None
    mbti_tf: Optional[str] = None
    mbti_jp: Optional[str] = None
    speaking_tone: Optional[str] = None


class UpdateAgentRequest(BaseModel):
    agent_name: Optional[str] = None
    persona: Optional[str] = None
    model: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    mbti_ei: Optional[str] = None
    mbti_sn: Optional[str] = None
    mbti_tf: Optional[str] = None
    mbti_jp: Optional[str] = None
    speaking_tone: Optional[str] = None


class AgentKeyResponse(BaseModel):
    key_id: str
    agent_name: str
    persona: str
    model: str
    avatar_url: str
    color: str
    gender: str
    mbti_ei: str
    mbti_sn: str
    mbti_tf: str
    mbti_jp: str
    speaking_tone: str
    api_key: str                # 발급 시에만 노출, 이후 조회 시 마스킹
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


class AgentKeySummary(BaseModel):
    key_id: str
    agent_name: str
    persona: str
    model: str
    avatar_url: str
    color: str
    gender: str
    mbti_ei: str
    mbti_sn: str
    mbti_tf: str
    mbti_jp: str
    speaking_tone: str
    api_key_masked: str         # "cwd_****...****"
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


class AgentVerifyResponse(BaseModel):
    agent_id: str
    agent_name: str
    is_valid: bool


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.post("", response_model=AgentKeyResponse, summary="에이전트 등록 및 API Key 발급")
async def create_agent(
    body: CreateAgentRequest,
    current_user: CurrentUser,
):
    try:
        agent = await create_agent_key(
            owner_uid=current_user.uid,
            seed=AgentProfileSeed(
                agent_name=body.agent_name,
                persona=body.persona,
                model=body.model,
                avatar_url=body.avatar_url,
                gender=body.gender,
                mbti_ei=body.mbti_ei,
                mbti_sn=body.mbti_sn,
                mbti_tf=body.mbti_tf,
                mbti_jp=body.mbti_jp,
                speaking_tone=body.speaking_tone,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return AgentKeyResponse(
        key_id=agent.key_id,
        agent_name=agent.agent_name,
        persona=agent.persona,
        model=agent.model,
        avatar_url=agent.avatar_url,
        color=agent.color,
        gender=agent.gender,
        mbti_ei=agent.mbti_ei,
        mbti_sn=agent.mbti_sn,
        mbti_tf=agent.mbti_tf,
        mbti_jp=agent.mbti_jp,
        speaking_tone=agent.speaking_tone,
        api_key=agent.api_key,
        is_active=agent.is_active,
        created_at=agent.created_at,
        last_used_at=agent.last_used_at,
    )


@router.get("/my", response_model=list[AgentKeySummary], summary="내 에이전트 목록")
async def list_my_agents(current_user: CurrentUser):
    agents = await get_agent_keys_by_owner(current_user.uid)
    return [
        AgentKeySummary(
            key_id=a.key_id,
            agent_name=a.agent_name,
            persona=a.persona,
            model=a.model,
            avatar_url=a.avatar_url,
            color=a.color,
            gender=a.gender,
            mbti_ei=a.mbti_ei,
            mbti_sn=a.mbti_sn,
            mbti_tf=a.mbti_tf,
            mbti_jp=a.mbti_jp,
            speaking_tone=a.speaking_tone,
            api_key_masked=f"{a.api_key[:8]}...{a.api_key[-4:]}",
            is_active=a.is_active,
            created_at=a.created_at,
            last_used_at=a.last_used_at,
        )
        for a in agents
    ]


@router.patch("/{key_id}", response_model=AgentKeySummary, summary="에이전트 정보 수정")
async def update_agent(
    key_id: str,
    body: UpdateAgentRequest,
    current_user: CurrentUser,
):
    agent = await AgentKey.find_one(
        AgentKey.key_id == key_id,
        AgentKey.owner_uid == current_user.uid,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다.")

    if body.agent_name is not None:
        agent.agent_name = body.agent_name
    if body.persona is not None:
        agent.persona = body.persona
    if body.model is not None:
        agent.model = body.model
    if body.avatar_url is not None:
        agent.avatar_url = body.avatar_url
    if body.gender is not None:
        agent.gender = body.gender
    if body.mbti_ei is not None:
        agent.mbti_ei = body.mbti_ei
    if body.mbti_sn is not None:
        agent.mbti_sn = body.mbti_sn
    if body.mbti_tf is not None:
        agent.mbti_tf = body.mbti_tf
    if body.mbti_jp is not None:
        agent.mbti_jp = body.mbti_jp
    if body.speaking_tone is not None:
        agent.speaking_tone = body.speaking_tone

    await agent.save()
    return AgentKeySummary(
        key_id=agent.key_id,
        agent_name=agent.agent_name,
        persona=agent.persona,
        model=agent.model,
        avatar_url=agent.avatar_url,
        color=agent.color,
        gender=agent.gender,
        mbti_ei=agent.mbti_ei,
        mbti_sn=agent.mbti_sn,
        mbti_tf=agent.mbti_tf,
        mbti_jp=agent.mbti_jp,
        speaking_tone=agent.speaking_tone,
        api_key_masked=f"{agent.api_key[:8]}...{agent.api_key[-4:]}",
        is_active=agent.is_active,
        created_at=agent.created_at,
        last_used_at=agent.last_used_at,
    )


@router.post("/verify", response_model=AgentVerifyResponse, summary="API Key 검증")
async def verify_agent(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
):
    """외부 에이전트가 접속 시 API Key를 검증합니다."""
    try:
        agent = await verify_agent_key(x_agent_key)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return AgentVerifyResponse(
        agent_id=agent.key_id,
        agent_name=agent.agent_name,
        is_valid=True,
    )
