# app/services/channel_service.py
"""
채널(Channel) 및 분기(Branch) 핵심 비즈니스 로직.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.models.channel import (
    Branch,
    Channel,
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
# Channel CRUD
# ─────────────────────────────────────────────

async def create_channel(
    title: str,
    topic: str,
    tags: list[str],
    agents: list[AgentProfile],
    creator_uid: Optional[str] = None,
) -> Channel:
    """새 채널 생성 (root branch 포함)."""
    root_branch_id = generate_branch_id(None, None, None)
    root_branch = Branch(
        branch_id=root_branch_id,
        channel_name="general",
        depth=0,
    )

    channel = Channel(
        title=title,
        topic=topic,
        tags=tags,
        agents=agents,
        creator_uid=creator_uid,
        root_branch_id=root_branch_id,
        branches={root_branch_id: root_branch},
    )
    await channel.insert()
    return channel


async def list_channels(
    tags: Optional[list[str]] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> list[Channel]:
    """채널 목록 조회 (태그 필터, 검색어 지원)."""
    query = Channel.find(Channel.status == "active")

    if tags:
        query = query.find({"tags": {"$in": tags}})
    if search:
        query = query.find({"$or": [
            {"title": {"$regex": search, "$options": "i"}},
            {"topic": {"$regex": search, "$options": "i"}},
        ]})

    return await query.sort(-Channel.created_at).skip(skip).limit(limit).to_list()


async def get_channel(channel_id: str) -> Optional[Channel]:
    return await Channel.get(channel_id)


# ─────────────────────────────────────────────
# Branch Operations
# ─────────────────────────────────────────────

async def create_branch(
    channel_id: str,
    parent_branch_id: str,
    fork_message_id: str,
    intervention_type: str,      # "replace" | "redirect"
    intervention_content: str,
    intervener_uid: str,
    channel_name: str = "general",
    data_opt_in: bool = False,
) -> tuple[Channel, Branch]:
    """
    특정 메시지 지점에서 새 분기를 생성합니다.

    - replace 개입: fork_message_id를 제외한 이전 메시지 복사, 원본 발화를 rejected_content에 저장
    - redirect 개입: fork_message_id를 포함한 이전 메시지 전체 복사 (대화 연장 지원)
    """
    channel = await Channel.get(channel_id)
    if not channel:
        raise ValueError("채널을 찾을 수 없습니다.")

    parent_branch = channel.branches.get(parent_branch_id)
    if not parent_branch:
        raise ValueError("부모 분기를 찾을 수 없습니다.")

    messages_before_fork: list[Message] = []
    rejected_content: Optional[str] = None

    for msg in parent_branch.messages:
        if msg.message_id == fork_message_id:
            msg.branch_count += 1
            if intervention_type == "replace":
                rejected_content = msg.content
                break
            else:
                # redirect 개입인 경우 fork 지점 메시지 자체도 새 분기에 그대로 포함함
                messages_before_fork.append(msg)
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
        data_opt_in=data_opt_in,
        rejected_content=rejected_content,
        messages=messages_before_fork,
        depth=parent_branch.depth + 1,
    )

    # 부모 브랜치 자식 목록 업데이트
    parent_branch.child_branch_ids.append(new_branch_id)

    # dict 업데이트 (Beanie는 embedded dict 변경 시 명시적 저장 필요)
    channel.branches[new_branch_id] = new_branch
    channel.updated_at = _utcnow()
    await channel.save()

    # 개입한 유저 stats 업데이트
    user = await User.find_one(User.uid == intervener_uid)
    if user:
        user.stats.branches_created += 1
        await user.save()

    return channel, new_branch


async def add_message_to_branch(
    channel_id: str,
    branch_id: str,
    message: Message,
) -> Channel:
    """분기에 새 메시지를 추가합니다."""
    channel = await Channel.get(channel_id)
    if not channel:
        raise ValueError("채널을 찾을 수 없습니다.")

    branch = channel.branches.get(branch_id)
    if not branch:
        raise ValueError("분기를 찾을 수 없습니다.")

    branch.messages.append(message)
    channel.updated_at = _utcnow()
    await channel.save()

    # 10턴마다 비동기로 에이전트 간의 관계 업데이트
    if len(branch.messages) % 10 == 0:
        import asyncio
        asyncio.create_task(update_agent_relationships_task(channel_id, branch_id))

    return channel


# ─────────────────────────────────────────────
# Interaction (좋아요 / 스크랩)
# ─────────────────────────────────────────────

async def toggle_like(
    uid: str,
    channel_id: str,
    branch_id: str,
) -> dict:
    """좋아요 토글. 반환: {liked: bool, count: int}"""
    channel = await Channel.get(channel_id)
    if not channel:
        raise ValueError("채널을 찾을 수 없습니다.")

    branch = channel.branches.get(branch_id)
    if not branch:
        raise ValueError("분기를 찾을 수 없습니다.")

    user = await User.find_one(User.uid == uid)
    if not user:
        raise ValueError("유저를 찾을 수 없습니다.")

    existing = await UserInteraction.find_one(
        UserInteraction.uid == uid,
        UserInteraction.channel_id == channel_id,
        UserInteraction.branch_id == branch_id,
        UserInteraction.interaction_type == INTERACTION_LIKE,
    )

    if existing:
        # 좋아요 취소
        await existing.delete()
        branch.likes = max(0, branch.likes - 1)
        channel.total_likes = max(0, channel.total_likes - 1)
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
            channel_id=channel_id,
            branch_id=branch_id,
            interaction_type=INTERACTION_LIKE,
        )
        await interaction.insert()
        branch.likes += 1
        channel.total_likes += 1
        user.liked_branches.append(branch_id)
        liked = True

        if branch.intervener_uid:
            intervener = await User.find_one(User.uid == branch.intervener_uid)
            if intervener:
                intervener.stats.likes_received += 1
                await intervener.save()

    channel.updated_at = _utcnow()
    await channel.save()
    await user.save()

    return {"liked": liked, "count": branch.likes}


async def toggle_scrap(
    uid: str,
    channel_id: str,
    branch_id: str,
) -> dict:
    """스크랩 토글. 반환: {scrapped: bool, count: int}"""
    channel = await Channel.get(channel_id)
    if not channel:
        raise ValueError("채널을 찾을 수 없습니다.")

    branch = channel.branches.get(branch_id)
    if not branch:
        raise ValueError("분기를 찾을 수 없습니다.")

    user = await User.find_one(User.uid == uid)
    if not user:
        raise ValueError("유저를 찾을 수 없습니다.")

    existing = await UserInteraction.find_one(
        UserInteraction.uid == uid,
        UserInteraction.channel_id == channel_id,
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
            channel_id=channel_id,
            branch_id=branch_id,
            interaction_type=INTERACTION_SCRAP,
        )
        await interaction.insert()
        branch.scraps += 1
        user.scrapped_branches.append(branch_id)
        scrapped = True

    channel.updated_at = _utcnow()
    await channel.save()
    await user.save()

    return {"scrapped": scrapped, "count": branch.scraps}


# ─────────────────────────────────────────────
# Branch Tree Serialization
# ─────────────────────────────────────────────

def serialize_branch_tree(channel: Channel) -> dict:
    """
    해시트리를 프론트엔드가 렌더링하기 좋은 트리 형태로 직렬화합니다.
    """
    def _build_node(branch_id: str) -> Optional[dict]:
        branch = channel.branches.get(branch_id)
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

    return _build_node(channel.root_branch_id) or {}


async def toggle_message_vote(
    uid: str,
    channel_id: str,
    branch_id: str,
    message_id: str,
    vote_type: str,
) -> dict:
    """메시지 추천/비추천 토글. 반환: {'success': bool, 'upvotes': int, 'downvotes': int, 'user_vote': Optional[str]}"""
    if vote_type not in (INTERACTION_UPVOTE, INTERACTION_DOWNVOTE):
        raise ValueError("Invalid vote type")

    channel = await Channel.get(channel_id)
    if not channel:
        raise ValueError("Channel not found")

    branch = channel.branches.get(branch_id)
    if not branch:
        raise ValueError("Branch not found")

    message = next((m for m in branch.messages if m.message_id == message_id), None)
    if not message:
        raise ValueError("Message not found")

    # 기존 투표 조회 (upvote 또는 downvote)
    existing = await UserInteraction.find_one(
        UserInteraction.uid == uid,
        UserInteraction.channel_id == channel_id,
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
            channel_id=channel_id,
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

    channel.updated_at = _utcnow()
    await channel.save()

    return {
        "success": True,
        "upvotes": message.upvotes,
        "downvotes": message.downvotes,
        "user_vote": user_vote,
    }


async def calculate_channel_preference_score(
    channel_id: str,
    channel_name: str,
) -> dict:
    """
    채널 내의 모든 브랜치와 메시지의 인터랙션을 취합하고 시간 감쇠(Time Decay)를 고려해 채널 선호도 점수를 계산합니다.
    """
    channel = await Channel.get(channel_id)
    if not channel:
        raise ValueError("Channel not found")

    channel_branches = [
        b for b in channel.branches.values() if b.channel_name == channel_name
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


async def update_agent_relationships_task(channel_id: str, branch_id: str):
    """
    비동기 백그라운드 태스크: 대화 로그를 기반으로 에이전트 간 관계를 추론하여 갱신합니다.
    """
    from app.services import agent_service
    from app.models.channel import AgentRelationship

    channel = await Channel.get(channel_id)
    if not channel:
        print(f"[update_agent_relationships_task] Channel {channel_id} not found.")
        return

    branch = channel.branches.get(branch_id)
    if not branch:
        print(f"[update_agent_relationships_task] Branch {branch_id} not found.")
        return

    # 대화 히스토리
    history = branch.messages

    # LLM 분석 실행 (Gemini Structured Outputs)
    analysis_result = await agent_service.analyze_agent_relationships(channel.agents, history)
    if not analysis_result:
        print("[update_agent_relationships_task] No relationship updates derived.")
        return

    # 기존 관계를 딕셔너리로 관리하여 갱신
    existing_rels = {f"{r.agent_id_a}-{r.agent_id_b}": r for r in getattr(channel, "relationships", []) or []}

    for item in analysis_result.relationships:
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
            trigger_message_id=item.trigger_message_id,
            trigger_message_content=item.trigger_message_content,
            updated_at=_utcnow()
        )

    channel.relationships = list(existing_rels.values())

    # 개별 에이전트 감정 상태(Mood) 갱신
    if getattr(channel, "agent_moods", None) is None:
        channel.agent_moods = {}

    for agent_id, mood in analysis_result.agent_moods.items():
        channel.agent_moods[agent_id] = mood

    channel.updated_at = _utcnow()
    await channel.save()
    print(f"[update_agent_relationships_task] Successfully updated relationships for Channel {channel_id}")
