# app/services/conversation_service.py
"""
대화(Conversation) 및 분기(Branch) 핵심 비즈니스 로직.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models.conversation import (
    Branch,
    Conversation,
    Message,
    AgentProfile,
    generate_branch_id,
)
from app.models.interaction import (
    UserInteraction,
    INTERACTION_LIKE,
    INTERACTION_SCRAP,
    INTERACTION_UPVOTE,
    INTERACTION_DOWNVOTE,
)
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Conversation CRUD
# ─────────────────────────────────────────────

async def create_conversation(
    title: str,
    topic: str,
    tags: list[str],
    agents: list[AgentProfile],
    creator_uid: Optional[str] = None,
) -> Conversation:
    """새 대화 세션 생성 (root branch 포함)."""
    root_branch_id = generate_branch_id(None, None, None)
    root_branch = Branch(
        branch_id=root_branch_id,
        channel_name="general",
        depth=0,
    )

    conv = Conversation(
        title=title,
        topic=topic,
        tags=tags,
        channels=["general"],
        agents=agents,
        creator_uid=creator_uid,
        root_branch_id=root_branch_id,
        branches={root_branch_id: root_branch},
    )
    await conv.insert()
    return conv


async def list_conversations(
    tags: Optional[list[str]] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> list[Conversation]:
    """대화 목록 조회 (태그 필터, 검색어 지원)."""
    query = Conversation.find(Conversation.status == "active")

    if tags:
        query = query.find({"tags": {"$in": tags}})
    if search:
        query = query.find({"$or": [
            {"title": {"$regex": search, "$options": "i"}},
            {"topic": {"$regex": search, "$options": "i"}},
        ]})

    return await query.sort(-Conversation.created_at).skip(skip).limit(limit).to_list()


async def get_conversation(conversation_id: str) -> Optional[Conversation]:
    return await Conversation.get(conversation_id)


# ─────────────────────────────────────────────
# Branch Operations
# ─────────────────────────────────────────────

async def create_branch(
    conversation_id: str,
    parent_branch_id: str,
    fork_message_id: str,
    intervention_type: str,      # "replace" | "redirect"
    intervention_content: str,
    intervener_uid: str,
    channel_name: str = "general",
) -> tuple[Conversation, Branch]:
    """
    특정 메시지 지점에서 새 분기를 생성합니다.

    1. fork_message_id 이전 메시지를 복사
    2. 새 branch_id 해시 생성
    3. Conversation.branches dict에 추가
    4. 부모 브랜치의 해당 메시지에 branch_count +1
    5. 부모 브랜치 child_branch_ids 업데이트
    """
    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("대화를 찾을 수 없습니다.")

    parent_branch = conv.branches.get(parent_branch_id)
    if not parent_branch:
        raise ValueError("부모 분기를 찾을 수 없습니다.")

    # fork 지점 이전 메시지 복사
    messages_before_fork: list[Message] = []
    for msg in parent_branch.messages:
        if msg.message_id == fork_message_id:
            # branch_count 증가
            msg.branch_count += 1
            break
        messages_before_fork.append(msg)

    new_branch_id = generate_branch_id(
        parent_branch_id, fork_message_id, intervention_content
    )

    new_branch = Branch(
        branch_id=new_branch_id,
        parent_branch_id=parent_branch_id,
        fork_message_id=fork_message_id,
        channel_name=channel_name,
        intervention_type=intervention_type,
        intervention_content=intervention_content,
        intervener_uid=intervener_uid,
        messages=messages_before_fork,
        depth=parent_branch.depth + 1,
    )

    # 부모 브랜치 자식 목록 업데이트
    parent_branch.child_branch_ids.append(new_branch_id)

    # dict 업데이트 (Beanie는 embedded dict 변경 시 명시적 저장 필요)
    conv.branches[new_branch_id] = new_branch
    conv.updated_at = _utcnow()
    await conv.save()

    # 개입한 유저 stats 업데이트
    user = await User.find_one(User.uid == intervener_uid)
    if user:
        user.stats.branches_created += 1
        await user.save()

    return conv, new_branch


async def add_message_to_branch(
    conversation_id: str,
    branch_id: str,
    message: Message,
) -> Conversation:
    """분기에 새 메시지를 추가합니다."""
    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("대화를 찾을 수 없습니다.")

    branch = conv.branches.get(branch_id)
    if not branch:
        raise ValueError("분기를 찾을 수 없습니다.")

    branch.messages.append(message)
    conv.updated_at = _utcnow()
    await conv.save()

    # 10턴마다 비동기로 에이전트 간의 관계 업데이트
    if len(branch.messages) % 10 == 0:
        import asyncio
        asyncio.create_task(update_agent_relationships_task(conversation_id, branch_id))

    return conv


# ─────────────────────────────────────────────
# Interaction (좋아요 / 스크랩)
# ─────────────────────────────────────────────

async def toggle_like(
    uid: str,
    conversation_id: str,
    branch_id: str,
) -> dict:
    """좋아요 토글. 반환: {liked: bool, count: int}"""
    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("대화를 찾을 수 없습니다.")

    branch = conv.branches.get(branch_id)
    if not branch:
        raise ValueError("분기를 찾을 수 없습니다.")

    user = await User.find_one(User.uid == uid)
    if not user:
        raise ValueError("유저를 찾을 수 없습니다.")

    existing = await UserInteraction.find_one(
        UserInteraction.uid == uid,
        UserInteraction.conversation_id == conversation_id,
        UserInteraction.branch_id == branch_id,
        UserInteraction.interaction_type == INTERACTION_LIKE,
    )

    if existing:
        # 좋아요 취소
        await existing.delete()
        branch.likes = max(0, branch.likes - 1)
        conv.total_likes = max(0, conv.total_likes - 1)
        if branch_id in user.liked_branches:
            user.liked_branches.remove(branch_id)
        liked = False

        # 에이전트 개입자에게 좋아요 반영
        if branch.intervener_uid:
            intervener = await User.find_one(User.uid == branch.intervener_uid)
            if intervener:
                intervener.stats.likes_received = max(0, intervener.stats.likes_received - 1)
                await intervener.save()
    else:
        # 좋아요 추가
        interaction = UserInteraction(
            uid=uid,
            conversation_id=conversation_id,
            branch_id=branch_id,
            interaction_type=INTERACTION_LIKE,
        )
        await interaction.insert()
        branch.likes += 1
        conv.total_likes += 1
        user.liked_branches.append(branch_id)
        liked = True

        if branch.intervener_uid:
            intervener = await User.find_one(User.uid == branch.intervener_uid)
            if intervener:
                intervener.stats.likes_received += 1
                await intervener.save()

    conv.updated_at = _utcnow()
    await conv.save()
    await user.save()

    return {"liked": liked, "count": branch.likes}


async def toggle_scrap(
    uid: str,
    conversation_id: str,
    branch_id: str,
) -> dict:
    """스크랩 토글. 반환: {scrapped: bool, count: int}"""
    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("대화를 찾을 수 없습니다.")

    branch = conv.branches.get(branch_id)
    if not branch:
        raise ValueError("분기를 찾을 수 없습니다.")

    user = await User.find_one(User.uid == uid)
    if not user:
        raise ValueError("유저를 찾을 수 없습니다.")

    existing = await UserInteraction.find_one(
        UserInteraction.uid == uid,
        UserInteraction.conversation_id == conversation_id,
        UserInteraction.branch_id == branch_id,
        UserInteraction.interaction_type == INTERACTION_SCRAP,
    )

    if existing:
        await existing.delete()
        branch.scraps = max(0, branch.scraps - 1)
        if branch_id in user.scrapped_branches:
            user.scrapped_branches.remove(branch_id)
        scrapped = False
    else:
        interaction = UserInteraction(
            uid=uid,
            conversation_id=conversation_id,
            branch_id=branch_id,
            interaction_type=INTERACTION_SCRAP,
        )
        await interaction.insert()
        branch.scraps += 1
        user.scrapped_branches.append(branch_id)
        scrapped = True

    conv.updated_at = _utcnow()
    await conv.save()
    await user.save()

    return {"scrapped": scrapped, "count": branch.scraps}


# ─────────────────────────────────────────────
# Branch Tree Serialization
# ─────────────────────────────────────────────

def serialize_branch_tree(conv: Conversation) -> dict:
    """
    해시트리를 프론트엔드가 렌더링하기 좋은 트리 형태로 직렬화합니다.
    """
    def _build_node(branch_id: str) -> Optional[dict]:
        branch = conv.branches.get(branch_id)
        if not branch:
            return None
        return {
            "branch_id": branch.branch_id,
            "parent_branch_id": branch.parent_branch_id,
            "fork_message_id": branch.fork_message_id,
            "channel_name": branch.channel_name,
            "intervention_type": branch.intervention_type,
            "intervention_content": branch.intervention_content,
            "intervener_uid": branch.intervener_uid,
            "depth": branch.depth,
            "likes": branch.likes,
            "scraps": branch.scraps,
            "message_count": len(branch.messages),
            "children": [
                _build_node(child_id)
                for child_id in branch.child_branch_ids
                if _build_node(child_id) is not None
            ],
        }

    return _build_node(conv.root_branch_id) or {}


async def add_channel(
    conversation_id: str,
    channel_name: str,
    description: str = "",
    rules: str = "",
    is_private: bool = False,
    invited_agent_ids: list[str] = None
) -> Conversation:
    """대화방(서버) 내 새로운 채널 등록 및 해당 채널의 루트 브랜치 생성."""
    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("대화를 찾을 수 없습니다.")

    if channel_name not in conv.channels:
        conv.channels.append(channel_name)

    # 해당 채널용 루트 브랜치 생성
    has_branch = any(b.channel_name == channel_name and b.parent_branch_id is None for b in conv.branches.values())
    if not has_branch:
        root_branch_id = generate_branch_id(None, None, channel_name)
        root_branch = Branch(
            branch_id=root_branch_id,
            channel_name=channel_name,
            depth=0,
        )
        conv.branches[root_branch_id] = root_branch

    # 추가 메타데이터 정보 저장
    if conv.channel_rules is None:
        conv.channel_rules = {}
    if conv.channel_descriptions is None:
        conv.channel_descriptions = {}
    if conv.channel_privacy is None:
        conv.channel_privacy = {}
    if conv.channel_agents is None:
        conv.channel_agents = {}

    conv.channel_rules[channel_name] = rules
    conv.channel_descriptions[channel_name] = description
    conv.channel_privacy[channel_name] = is_private
    conv.channel_agents[channel_name] = invited_agent_ids or []

    conv.updated_at = _utcnow()
    await conv.save()
    return conv


async def toggle_message_vote(
    uid: str,
    conversation_id: str,
    branch_id: str,
    message_id: str,
    vote_type: str,
) -> dict:
    """메시지 추천/비추천 토글. 반환: {'success': bool, 'upvotes': int, 'downvotes': int, 'user_vote': Optional[str]}"""
    if vote_type not in (INTERACTION_UPVOTE, INTERACTION_DOWNVOTE):
        raise ValueError("Invalid vote type")

    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("Conversation not found")

    branch = conv.branches.get(branch_id)
    if not branch:
        raise ValueError("Branch not found")

    message = next((m for m in branch.messages if m.message_id == message_id), None)
    if not message:
        raise ValueError("Message not found")

    # 기존 투표 조회 (upvote 또는 downvote)
    existing = await UserInteraction.find_one(
        UserInteraction.uid == uid,
        UserInteraction.conversation_id == conversation_id,
        UserInteraction.branch_id == branch_id,
        UserInteraction.message_id == message_id,
        {"interaction_type": {"$in": [INTERACTION_UPVOTE, INTERACTION_DOWNVOTE]}},
    )

    user_vote = None
    if existing:
        if existing.interaction_type == vote_type:
            # 같은 투표 클릭 시 투표 취소
            await existing.delete()
            if vote_type == INTERACTION_UPVOTE:
                message.upvotes = max(0, message.upvotes - 1)
            else:
                message.downvotes = max(0, message.downvotes - 1)
        else:
            # 다른 투표 클릭 시 기존 투표 변경 (취소 후 새로 등록)
            if existing.interaction_type == INTERACTION_UPVOTE:
                message.upvotes = max(0, message.upvotes - 1)
                message.downvotes += 1
            else:
                message.downvotes = max(0, message.downvotes - 1)
                message.upvotes += 1
            existing.interaction_type = vote_type
            await existing.save()
            user_vote = vote_type
    else:
        # 투표 신규 등록
        interaction = UserInteraction(
            uid=uid,
            conversation_id=conversation_id,
            branch_id=branch_id,
            message_id=message_id,
            interaction_type=vote_type,
        )
        await interaction.insert()
        if vote_type == INTERACTION_UPVOTE:
            message.upvotes += 1
        else:
            message.downvotes += 1
        user_vote = vote_type

    conv.updated_at = _utcnow()
    await conv.save()

    return {
        "success": True,
        "upvotes": message.upvotes,
        "downvotes": message.downvotes,
        "user_vote": user_vote,
    }


async def calculate_channel_preference_score(
    conversation_id: str,
    channel_name: str,
) -> dict:
    """
    채널 내의 모든 브랜치와 메시지의 인터랙션을 취합하고 시간 감쇠(Time Decay)를 고려해 채널 선호도 점수를 계산합니다.
    """
    conv = await Conversation.get(conversation_id)
    if not conv:
        raise ValueError("Conversation not found")

    channel_branches = [
        b for b in conv.branches.values() if b.channel_name == channel_name
    ]

    w_branch = 5.0
    w_like = 2.0
    w_scrap = 3.0
    w_up = 1.0
    w_down = 1.5

    total_score = 0.0
    total_branches = len(channel_branches)
    total_likes = 0
    total_scraps = 0
    total_upvotes = 0
    total_downvotes = 0

    now = datetime.now(timezone.utc)

    for b in channel_branches:
        likes = b.likes or 0
        scraps = b.scraps or 0
        total_likes += likes
        total_scraps += scraps

        branch_upvotes = 0
        branch_downvotes = 0
        for m in b.messages:
            m_up = getattr(m, "upvotes", 0) or 0
            m_down = getattr(m, "downvotes", 0) or 0
            branch_upvotes += m_up
            branch_downvotes += m_down

        total_upvotes += branch_upvotes
        total_downvotes += branch_downvotes

        # Branch activity (deeper tree branching gives slightly more score)
        branch_activity = w_branch * (1.0 + math.log1p(len(b.child_branch_ids or [])))

        # Raw score summation
        branch_raw_score = (
            branch_activity
            + (w_like * likes)
            + (w_scrap * scraps)
            + (w_up * branch_upvotes)
            - (w_down * branch_downvotes)
        )

        # Time decay: T_age in hours. Decay = 1 / (T_age + 2)^1.5
        b_created_at = b.created_at.replace(tzinfo=timezone.utc) if b.created_at.tzinfo is None else b.created_at
        age_delta = now - b_created_at
        age_in_hours = age_delta.total_seconds() / 3600.0
        decay_factor = 1.0 / ((age_in_hours + 2.0) ** 1.5)

        total_score += branch_raw_score * decay_factor

    return {
        "channel_name": channel_name,
        "score": round(total_score, 4),
        "metrics": {
            "total_branches": total_branches,
            "total_likes": total_likes,
            "total_scraps": total_scraps,
            "total_upvotes": total_upvotes,
            "total_downvotes": total_downvotes,
        },
    }


async def update_agent_relationships_task(conversation_id: str, branch_id: str):
    """
    비동기 백그라운드 태스크: 대화 로그를 기반으로 에이전트 간 관계를 추론하여 갱신합니다.
    """
    from app.services import agent_service
    from app.models.conversation import AgentRelationship

    conv = await Conversation.get(conversation_id)
    if not conv:
        print(f"[update_agent_relationships_task] Conversation {conversation_id} not found.")
        return

    branch = conv.branches.get(branch_id)
    if not branch:
        print(f"[update_agent_relationships_task] Branch {branch_id} not found.")
        return

    # 현재 채널의 활성화된 에이전트
    channel_agents_ids = (conv.channel_agents or {}).get(branch.channel_name, [])
    if channel_agents_ids:
        active_agents = [a for a in conv.agents if a.agent_id in channel_agents_ids]
    else:
        active_agents = conv.agents

    # 대화 히스토리
    history = branch.messages

    # LLM 분석 실행 (Gemini Structured Outputs)
    analyzed_items = await agent_service.analyze_agent_relationships(active_agents, history)
    if not analyzed_items:
        print("[update_agent_relationships_task] No relationship updates derived.")
        return

    # 기존 관계를 딕셔너리로 관리하여 갱신
    existing_rels = {f"{r.agent_id_a}-{r.agent_id_b}": r for r in getattr(conv, "relationships", []) or []}

    for item in analyzed_items:
        # 순서 정렬하여 유니크 키 보장 (단방향 쌍 저장)
        sorted_ids = sorted([item.agent_id_a, item.agent_id_b])
        key = f"{sorted_ids[0]}-{sorted_ids[1]}"

        existing_rels[key] = AgentRelationship(
            agent_id_a=sorted_ids[0],
            agent_id_b=sorted_ids[1],
            affinity=item.affinity,
            relationship_label=item.relationship_label,
            sentiment=item.sentiment,
            description=item.description,
            updated_at=_utcnow()
        )

    conv.relationships = list(existing_rels.values())
    conv.updated_at = _utcnow()
    await conv.save()
    print(f"[update_agent_relationships_task] Successfully updated relationships for Conversation {conversation_id}")
