import pytest
from datetime import datetime, timedelta, timezone

from app.models.channel import AgentProfile, Branch, Channel, Message
from app.models.memory import MemoryItem
from app.services.memory_service import (
    extract_branch_memory_candidates,
    retrieve_agent_turn_memories,
)

pytestmark = pytest.mark.asyncio


async def test_extract_branch_memory_candidates_when_branch_completed():
    branch = Branch(
        branch_id="branch-memory-1",
        status="completed",
        messages=[
            Message(message_id="msg-1", agent_id="agent-1", content="첫 대화"),
            Message(message_id="msg-2", agent_id="agent-1", content="마지막 대화"),
        ],
    )
    channel = Channel(
        title="기억 테스트",
        topic="두 에이전트가 오래된 약속을 확인한다",
        agents=[AgentProfile(agent_id="agent-1", name="Ari", persona="차분한 에이전트")],
        root_branch_id=branch.branch_id,
        branches={branch.branch_id: branch},
        creator_uid="user-memory",
    )
    await channel.insert()

    memories = await extract_branch_memory_candidates(channel, branch)

    assert len(memories) == 1
    assert branch.memory_candidate_ids == [memories[0].memory_id]
    assert memories[0].approved is False

    await channel.delete()
    for memory in memories:
        await memory.delete()


async def test_retrieve_agent_turn_memories_returns_only_approved_items():
    approved = MemoryItem(
        owner_type="agent",
        owner_id="agent-memory-1",
        kind="channel_lore",
        scope="agent_only",
        summary="Ari는 오래된 약속을 중요하게 여긴다.",
        source={
            "channel_id": "channel-memory-1",
            "branch_id": "branch-memory-1",
            "message_ids": ["msg-1"],
        },
        approved=True,
    )
    pending = MemoryItem(
        owner_type="agent",
        owner_id="agent-memory-1",
        kind="channel_lore",
        scope="agent_only",
        summary="아직 승인되지 않은 기억",
        source={
            "channel_id": "channel-memory-1",
            "branch_id": "branch-memory-1",
            "message_ids": ["msg-2"],
        },
        approved=False,
    )
    await approved.insert()
    await pending.insert()

    memories = await retrieve_agent_turn_memories(agent_id="agent-memory-1")

    assert [memory.memory_id for memory in memories] == [approved.memory_id]

    await approved.delete()
    await pending.delete()


async def test_retrieve_agent_turn_memories_excludes_expired_and_wrong_scope():
    expired = MemoryItem(
        owner_type="agent",
        owner_id="agent-memory-2",
        kind="channel_lore",
        scope="agent_only",
        summary="만료된 기억",
        source={
            "channel_id": "channel-memory-2",
            "branch_id": "branch-memory-2",
            "message_ids": ["msg-1"],
        },
        approved=True,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    private = MemoryItem(
        owner_type="agent",
        owner_id="agent-memory-2",
        kind="channel_lore",
        scope="private",
        summary="검색되면 안 되는 개인 기억",
        source={
            "channel_id": "channel-memory-2",
            "branch_id": "branch-memory-2",
            "message_ids": ["msg-2"],
        },
        approved=True,
    )
    usable = MemoryItem(
        owner_type="agent",
        owner_id="agent-memory-2",
        kind="channel_lore",
        scope="agent_only",
        summary="검색 가능한 기억",
        source={
            "channel_id": "channel-memory-2",
            "branch_id": "branch-memory-2",
            "message_ids": ["msg-3"],
        },
        approved=True,
    )
    await expired.insert()
    await private.insert()
    await usable.insert()

    memories = await retrieve_agent_turn_memories(agent_id="agent-memory-2")

    assert [memory.memory_id for memory in memories] == [usable.memory_id]

    await expired.delete()
    await private.delete()
    await usable.delete()
