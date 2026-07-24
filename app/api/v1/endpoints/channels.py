# app/api/v1/endpoints/channels.py
"""
채널(Channel) 및 분기(Branch) API 엔드포인트.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from app.core.security import CurrentUser, CurrentUserOptional
from app.models.channel import AgentProfile, Branch, Channel
from app.models.interaction import UserInteraction
from app.services import channel_service
from app.services.prompt_guard_service import PromptInjectionBlockedError

router = APIRouter(prefix="/channels", tags=["Channels"])


# ─────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────

class AgentProfileIn(BaseModel):
    agent_id: str
    name: str
    persona: str
    model: str = "gemini-2.0-flash"
    runtime_mode: str = "platform"
    avatar_url: str = ""


class CreateChannelRequest(BaseModel):
    title: str
    topic: str
    tags: list[str] = []
    agents: list[AgentProfileIn]


class CreateBranchRequest(BaseModel):
    parent_branch_id: str
    fork_message_id: str
    intervention_type: str              # "replace" | "redirect"
    intervention_content: str
    channel_name: str = "general"


class MessageOut(BaseModel):
    message_id: str
    agent_id: str
    content: str
    created_at: datetime
    branch_count: int
    upvotes: int = 0
    downvotes: int = 0
    user_vote: Optional[str] = None


class BranchOut(BaseModel):
    branch_id: str
    parent_branch_id: Optional[str]
    fork_message_id: Optional[str]
    channel_name: str
    intervention_type: Optional[str]
    intervention_content: Optional[str]
    intervener_uid: Optional[str]
    data_opt_in: bool
    rejected_content: Optional[str] = None
    child_branch_ids: list[str]
    memory_candidate_ids: list[str] = []
    safety_events: list[str] = []
    depth: int
    likes: int
    scraps: int
    status: str
    message_count: int
    created_at: datetime


class ChannelSummaryOut(BaseModel):
    id: str
    title: str
    topic: str
    tags: list[str]
    agent_count: int
    total_likes: int
    branch_count: int
    status: str
    created_at: datetime


class AgentRelationshipOut(BaseModel):
    agent_id_a: str
    agent_id_b: str
    affinity: int
    relationship_label: str
    sentiment: str
    description: Optional[str] = None
    trigger_message_id: Optional[str] = None
    trigger_message_content: Optional[str] = None
    updated_at: datetime


class ChannelDetailOut(BaseModel):
    id: str
    title: str
    topic: str
    tags: list[str]
    agents: list[AgentProfileIn]
    relationships: list[AgentRelationshipOut] = []
    agent_moods: dict[str, str] = {}
    root_branch_id: str
    branch_tree: dict               # 해시트리 직렬화 결과
    total_likes: int
    status: str
    creator_uid: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InteractionResponse(BaseModel):
    success: bool
    count: int
    state: bool                     # liked/scrapped 여부


class MessageVoteResponse(BaseModel):
    success: bool
    upvotes: int
    downvotes: int
    user_vote: Optional[str] = None


class ChannelMetrics(BaseModel):
    total_branches: int
    total_likes: int
    total_scraps: int
    total_upvotes: int
    total_downvotes: int


class ChannelScoreResponse(BaseModel):
    channel_name: str
    score: float
    metrics: ChannelMetrics


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.get("", response_model=list[ChannelSummaryOut], summary="채널 목록 조회")
async def list_channels(
    tags: Optional[str] = Query(None, description="콤마로 구분된 태그 (예: ai,ethics)"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    convs = await channel_service.list_channels(
        tags=tag_list, search=search, skip=skip, limit=limit
    )
    return [
        ChannelSummaryOut(
            id=str(c.id),
            title=c.title,
            topic=c.topic,
            tags=c.tags,
            agent_count=len(c.agents),
            total_likes=c.total_likes,
            branch_count=len(c.branches),
            status=c.status,
            created_at=c.created_at,
        )
        for c in convs
    ]


@router.post("", response_model=ChannelDetailOut, summary="채널 생성")
async def create_channel(
    body: CreateChannelRequest,
    current_user: CurrentUser,
):
    agents = [
        AgentProfile(
            agent_id=a.agent_id,
            name=a.name,
            persona=a.persona,
            model=a.model,
            runtime_mode=a.runtime_mode,
            avatar_url=a.avatar_url,
        )
        for a in body.agents
    ]
    try:
        conv = await channel_service.create_channel(
            title=body.title,
            topic=body.topic,
            tags=body.tags,
            agents=agents,
            creator_uid=current_user.uid,
        )
    except PromptInjectionBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _channel_to_detail(conv)


@router.get("/{channel_id}", response_model=ChannelDetailOut, summary="채널 상세 조회")
async def get_channel(channel_id: str):
    conv = await channel_service.get_channel(channel_id)
    if not conv:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
    return _channel_to_detail(conv)


@router.get("/{channel_id}/branches/{branch_id}", response_model=dict, summary="특정 분기 메시지 조회")
async def get_branch_messages(
    channel_id: str,
    branch_id: str,
    current_user: CurrentUserOptional,
):
    conv = await channel_service.get_channel(channel_id)
    if not conv:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
    branch = conv.branches.get(branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="분기를 찾을 수 없습니다.")

    user_votes = {}
    if current_user:
        interactions = await UserInteraction.find(
            UserInteraction.uid == current_user.uid,
            UserInteraction.channel_id == channel_id,
            UserInteraction.branch_id == branch_id,
            {"interaction_type": {"$in": ["upvote", "downvote"]}}
        ).to_list()
        user_votes = {i.message_id: i.interaction_type for i in interactions if i.message_id}

    return {
        "branch_id": branch.branch_id,
        "messages": [
            MessageOut(
                message_id=m.message_id,
                agent_id=m.agent_id,
                content=m.content,
                created_at=m.created_at,
                branch_count=m.branch_count,
                upvotes=getattr(m, "upvotes", 0) or 0,
                downvotes=getattr(m, "downvotes", 0) or 0,
                user_vote=user_votes.get(m.message_id)
            ).model_dump()
            for m in branch.messages
        ],
    }


@router.post("/{channel_id}/branches", response_model=BranchOut, summary="분기 생성 (인간 개입)")
async def create_branch(
    channel_id: str,
    body: CreateBranchRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    if body.intervention_type not in ("replace", "redirect"):
        raise HTTPException(status_code=400, detail="intervention_type은 'replace' 또는 'redirect'이어야 합니다.")

    try:
        _, branch = await channel_service.create_branch(
            channel_id=channel_id,
            parent_branch_id=body.parent_branch_id,
            fork_message_id=body.fork_message_id,
            intervention_type=body.intervention_type,
            intervention_content=body.intervention_content,
            intervener_uid=current_user.uid,
            channel_name=body.channel_name,
            data_opt_in=current_user.data_opt_in,
        )
    except PromptInjectionBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 비동기로 에이전트 간의 관계 업데이트
    background_tasks.add_task(
        channel_service.update_agent_relationships_task,
        channel_id,
        branch.branch_id
    )

    return _branch_to_out(branch)


@router.post("/{channel_id}/branches/{branch_id}/like", response_model=InteractionResponse, summary="좋아요 토글")
async def toggle_like(
    channel_id: str,
    branch_id: str,
    current_user: CurrentUser,
):
    result = await channel_service.toggle_like(
        uid=current_user.uid,
        channel_id=channel_id,
        branch_id=branch_id,
    )
    return InteractionResponse(success=True, count=result["count"], state=result["liked"])


@router.post("/{channel_id}/branches/{branch_id}/scrap", response_model=InteractionResponse, summary="스크랩 토글")
async def toggle_scrap(
    channel_id: str,
    branch_id: str,
    current_user: CurrentUser,
):
    result = await channel_service.toggle_scrap(
        uid=current_user.uid,
        channel_id=channel_id,
        branch_id=branch_id,
    )
    return InteractionResponse(success=True, count=result["count"], state=result["scrapped"])


@router.post("/{channel_id}/branches/{branch_id}/messages/{message_id}/upvote", response_model=MessageVoteResponse, summary="메시지 추천 토글")
async def toggle_message_upvote(
    channel_id: str,
    branch_id: str,
    message_id: str,
    current_user: CurrentUser,
):
    try:
        res = await channel_service.toggle_message_vote(
            uid=current_user.uid,
            channel_id=channel_id,
            branch_id=branch_id,
            message_id=message_id,
            vote_type="upvote",
        )
        return MessageVoteResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{channel_id}/branches/{branch_id}/messages/{message_id}/downvote", response_model=MessageVoteResponse, summary="메시지 비추천 토글")
async def toggle_message_downvote(
    channel_id: str,
    branch_id: str,
    message_id: str,
    current_user: CurrentUser,
):
    try:
        res = await channel_service.toggle_message_vote(
            uid=current_user.uid,
            channel_id=channel_id,
            branch_id=branch_id,
            message_id=message_id,
            vote_type="downvote",
        )
        return MessageVoteResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{channel_id}/score", response_model=ChannelScoreResponse, summary="채널 선호도 점수 계산")
async def get_channel_preference_score(
    channel_id: str,
):
    try:
        res = await channel_service.calculate_channel_preference_score(
            channel_id=channel_id,
            channel_name="general",
        )
        return ChannelScoreResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _channel_to_detail(channel: Channel) -> ChannelDetailOut:
    return ChannelDetailOut(
        id=str(channel.id),
        title=channel.title,
        topic=channel.topic,
        tags=channel.tags,
        agents=[
            AgentProfileIn(
                agent_id=a.agent_id,
                name=a.name,
                persona=a.persona,
                model=a.model,
                runtime_mode=getattr(a, "runtime_mode", "platform"),
                avatar_url=a.avatar_url,
            )
            for a in channel.agents
        ],
        relationships=[
            AgentRelationshipOut(
                agent_id_a=r.agent_id_a,
                agent_id_b=r.agent_id_b,
                affinity=r.affinity,
                relationship_label=r.relationship_label,
                sentiment=getattr(r, "sentiment", "neutral"),
                description=r.description,
                trigger_message_id=getattr(r, "trigger_message_id", None),
                trigger_message_content=getattr(r, "trigger_message_content", None),
                updated_at=r.updated_at,
            )
            for r in getattr(channel, "relationships", []) or []
        ],
        agent_moods=getattr(channel, "agent_moods", {}) or {},
        root_branch_id=channel.root_branch_id,
        branch_tree=channel_service.serialize_branch_tree(channel),
        total_likes=channel.total_likes,
        status=channel.status,
        creator_uid=channel.creator_uid,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


def _branch_to_out(branch: Branch) -> BranchOut:
    return BranchOut(
        branch_id=branch.branch_id,
        parent_branch_id=branch.parent_branch_id,
        fork_message_id=branch.fork_message_id,
        channel_name=branch.channel_name,
        intervention_type=branch.intervention_type,
        intervention_content=branch.intervention_content,
        intervener_uid=branch.intervener_uid,
        data_opt_in=getattr(branch, "data_opt_in", False),
        rejected_content=getattr(branch, "rejected_content", None),
        child_branch_ids=branch.child_branch_ids,
        memory_candidate_ids=branch.memory_candidate_ids,
        safety_events=branch.safety_events,
        depth=branch.depth,
        likes=branch.likes,
        scraps=branch.scraps,
        status=branch.status,
        message_count=len(branch.messages),
        created_at=branch.created_at,
    )
