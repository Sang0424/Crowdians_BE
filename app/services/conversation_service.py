# app/services/conversation_service.py
"""
대화(Conversation) 및 분기(Branch) 핵심 비즈니스 로직.
"""

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
from app.models.interaction import UserInteraction, INTERACTION_LIKE, INTERACTION_SCRAP
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
        depth=0,
    )

    conv = Conversation(
        title=title,
        topic=topic,
        tags=tags,
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
