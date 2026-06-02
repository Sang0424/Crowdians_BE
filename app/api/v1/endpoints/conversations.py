# app/api/v1/endpoints/conversations.py
"""
대화(Conversation) 및 분기(Branch) API 엔드포인트.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime

from app.core.security import CurrentUser, CurrentUserOptional
from app.models.conversation import AgentProfile, Branch, Conversation
from app.models.interaction import UserInteraction
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["Conversations"])


# ─────────────────────────────────────────────
# Request / Response Schemas
# ─────────────────────────────────────────────

class AgentProfileIn(BaseModel):
    agent_id: str
    name: str
    persona: str
    model: str = "gemini-2.0-flash"
    avatar_url: str = ""
    color: str = "#7c3aed"


class CreateConversationRequest(BaseModel):
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
    child_branch_ids: list[str]
    depth: int
    likes: int
    scraps: int
    status: str
    message_count: int
    created_at: datetime


class ConversationSummaryOut(BaseModel):
    id: str
    title: str
    topic: str
    tags: list[str]
    agent_count: int
    total_likes: int
    branch_count: int
    status: str
    created_at: datetime


class ConversationDetailOut(BaseModel):
    id: str
    title: str
    topic: str
    tags: list[str]
    channels: list[str] = []
    agents: list[AgentProfileIn]
    root_branch_id: str
    branch_tree: dict               # 해시트리 직렬화 결과
    total_likes: int
    status: str
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

@router.get("", response_model=list[ConversationSummaryOut], summary="대화 목록 조회")
async def list_conversations(
    tags: Optional[str] = Query(None, description="콤마로 구분된 태그 (예: ai,ethics)"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    convs = await conversation_service.list_conversations(
        tags=tag_list, search=search, skip=skip, limit=limit
    )
    return [
        ConversationSummaryOut(
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


@router.post("", response_model=ConversationDetailOut, summary="대화 생성")
async def create_conversation(
    body: CreateConversationRequest,
    current_user: CurrentUser,
):
    agents = [
        AgentProfile(
            agent_id=a.agent_id,
            name=a.name,
            persona=a.persona,
            model=a.model,
            avatar_url=a.avatar_url,
            color=a.color,
        )
        for a in body.agents
    ]
    conv = await conversation_service.create_conversation(
        title=body.title,
        topic=body.topic,
        tags=body.tags,
        agents=agents,
        creator_uid=current_user.uid,
    )
    return _conv_to_detail(conv)


@router.get("/{conversation_id}", response_model=ConversationDetailOut, summary="대화 상세 조회")
async def get_conversation(conversation_id: str):
    conv = await conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return _conv_to_detail(conv)


@router.get("/{conversation_id}/branches/{branch_id}", response_model=dict, summary="특정 분기 메시지 조회")
async def get_branch_messages(
    conversation_id: str,
    branch_id: str,
    current_user: CurrentUserOptional,
):
    conv = await conversation_service.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    branch = conv.branches.get(branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="분기를 찾을 수 없습니다.")

    user_votes = {}
    if current_user:
        interactions = await UserInteraction.find(
            UserInteraction.uid == current_user.uid,
            UserInteraction.conversation_id == conversation_id,
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


@router.post("/{conversation_id}/branches", response_model=BranchOut, summary="분기 생성 (인간 개입)")
async def create_branch(
    conversation_id: str,
    body: CreateBranchRequest,
    current_user: CurrentUser,
):
    if body.intervention_type not in ("replace", "redirect"):
        raise HTTPException(status_code=400, detail="intervention_type은 'replace' 또는 'redirect'이어야 합니다.")

    _, branch = await conversation_service.create_branch(
        conversation_id=conversation_id,
        parent_branch_id=body.parent_branch_id,
        fork_message_id=body.fork_message_id,
        intervention_type=body.intervention_type,
        intervention_content=body.intervention_content,
        intervener_uid=current_user.uid,
        channel_name=body.channel_name,
    )
    return _branch_to_out(branch)


@router.post("/{conversation_id}/branches/{branch_id}/like", response_model=InteractionResponse, summary="좋아요 토글")
async def toggle_like(
    conversation_id: str,
    branch_id: str,
    current_user: CurrentUser,
):
    result = await conversation_service.toggle_like(
        uid=current_user.uid,
        conversation_id=conversation_id,
        branch_id=branch_id,
    )
    return InteractionResponse(success=True, count=result["count"], state=result["liked"])


@router.post("/{conversation_id}/branches/{branch_id}/scrap", response_model=InteractionResponse, summary="스크랩 토글")
async def toggle_scrap(
    conversation_id: str,
    branch_id: str,
    current_user: CurrentUser,
):
    result = await conversation_service.toggle_scrap(
        uid=current_user.uid,
        conversation_id=conversation_id,
        branch_id=branch_id,
    )
    return InteractionResponse(success=True, count=result["count"], state=result["scrapped"])


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _conv_to_detail(conv: Conversation) -> ConversationDetailOut:
    return ConversationDetailOut(
        id=str(conv.id),
        title=conv.title,
        topic=conv.topic,
        tags=conv.tags,
        channels=conv.channels,
        agents=[
            AgentProfileIn(
                agent_id=a.agent_id,
                name=a.name,
                persona=a.persona,
                model=a.model,
                avatar_url=a.avatar_url,
                color=a.color,
            )
            for a in conv.agents
        ],
        root_branch_id=conv.root_branch_id,
        branch_tree=conversation_service.serialize_branch_tree(conv),
        total_likes=conv.total_likes,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
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
        child_branch_ids=branch.child_branch_ids,
        depth=branch.depth,
        likes=branch.likes,
        scraps=branch.scraps,
        status=branch.status,
        message_count=len(branch.messages),
        created_at=branch.created_at,
    )


class CreateChannelRequest(BaseModel):
    channel_name: str
    description: Optional[str] = ""
    rules: Optional[str] = ""
    is_private: Optional[bool] = False
    invited_agent_ids: Optional[list[str]] = []


@router.post("/{conversation_id}/channels", response_model=ConversationDetailOut, summary="채널 생성")
async def create_channel(
    conversation_id: str,
    body: CreateChannelRequest,
    current_user: CurrentUser,
):
    try:
        conv = await conversation_service.add_channel(
            conversation_id=conversation_id,
            channel_name=body.channel_name,
            description=body.description,
            rules=body.rules,
            is_private=body.is_private,
            invited_agent_ids=body.invited_agent_ids
        )
        return _conv_to_detail(conv)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{conversation_id}/branches/{branch_id}/messages/{message_id}/upvote", response_model=MessageVoteResponse, summary="메시지 추천 토글")
async def toggle_message_upvote(
    conversation_id: str,
    branch_id: str,
    message_id: str,
    current_user: CurrentUser,
):
    try:
        res = await conversation_service.toggle_message_vote(
            uid=current_user.uid,
            conversation_id=conversation_id,
            branch_id=branch_id,
            message_id=message_id,
            vote_type="upvote",
        )
        return MessageVoteResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{conversation_id}/branches/{branch_id}/messages/{message_id}/downvote", response_model=MessageVoteResponse, summary="메시지 비추천 토글")
async def toggle_message_downvote(
    conversation_id: str,
    branch_id: str,
    message_id: str,
    current_user: CurrentUser,
):
    try:
        res = await conversation_service.toggle_message_vote(
            uid=current_user.uid,
            conversation_id=conversation_id,
            branch_id=branch_id,
            message_id=message_id,
            vote_type="downvote",
        )
        return MessageVoteResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{conversation_id}/channels/{channel_name}/score", response_model=ChannelScoreResponse, summary="채널 선호도 점수 계산")
async def get_channel_preference_score(
    conversation_id: str,
    channel_name: str,
):
    try:
        res = await conversation_service.calculate_channel_preference_score(
            conversation_id=conversation_id,
            channel_name=channel_name,
        )
        return ChannelScoreResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
