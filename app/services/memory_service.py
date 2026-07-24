from datetime import datetime, timezone

from app.models.channel import Branch, Channel
from app.models.memory import (
    MemoryItem,
    MemoryKind,
    MemoryOwnerType,
    MemoryScope,
    MemorySource,
)
from app.services.prompt_guard_service import (
    PromptInjectionBlockedError,
    PromptSurface,
    require_safe_prompt_text,
)


def _source_message_ids(branch: Branch) -> list[str]:
    return [message.message_id for message in branch.messages]


def _channel_id(channel: Channel) -> str:
    return str(channel.id) if channel.id is not None else ""


def _safe_memory_items(items: list[MemoryItem]) -> list[MemoryItem]:
    safe_items: list[MemoryItem] = []
    for item in items:
        try:
            require_safe_prompt_text(PromptSurface.MEMORY_SUMMARY, item.summary)
        except PromptInjectionBlockedError:
            continue
        safe_items.append(item)
    return safe_items


def _usable_memories(
    memories: list[MemoryItem],
    allowed_scopes: set[MemoryScope],
    now: datetime,
) -> list[MemoryItem]:
    usable: list[MemoryItem] = []
    for memory in memories:
        if memory.scope not in allowed_scopes:
            continue
        expires_at = memory.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at is not None and expires_at <= now:
            continue
        usable.append(memory)
    return usable


async def extract_branch_memory_candidates(channel: Channel, branch: Branch) -> list[MemoryItem]:
    if branch.status != "completed":
        return []

    channel_id = _channel_id(channel)
    existing = await MemoryItem.find(
        MemoryItem.source.channel_id == channel_id,
        MemoryItem.source.branch_id == branch.branch_id,
    ).count()
    if existing > 0:
        return []

    source = MemorySource(
        channel_id=channel_id,
        branch_id=branch.branch_id,
        message_ids=_source_message_ids(branch),
    )
    summaries: list[MemoryItem] = [
        MemoryItem(
            owner_type=MemoryOwnerType.CHANNEL,
            owner_id=channel_id,
            kind=MemoryKind.CHANNEL_LORE,
            scope=MemoryScope.CHANNEL,
            summary=f"'{channel.title}' 채널에서 '{channel.topic}' 상황으로 15턴 대화가 완료되었습니다.",
            source=source,
            confidence=0.7,
        )
    ]

    for relationship in channel.relationships:
        if relationship.description is None:
            continue

        summaries.append(
            MemoryItem(
                owner_type=MemoryOwnerType.CHANNEL,
                owner_id=channel_id,
                kind=MemoryKind.AGENT_RELATIONSHIP,
                scope=MemoryScope.CHANNEL,
                summary=(
                    f"{relationship.agent_id_a}와 {relationship.agent_id_b}의 관계는 "
                    f"{relationship.relationship_label}이며, 현재 맥락은 '{relationship.description}'입니다."
                ),
                source=source,
                confidence=0.65,
            )
        )

    safe_summaries = _safe_memory_items(summaries)
    for memory in safe_summaries:
        await memory.insert()

    branch.memory_candidate_ids.extend(memory.memory_id for memory in safe_summaries)
    return safe_summaries


async def retrieve_agent_turn_memories(
    agent_id: str,
    channel_id: str | None = None,
    limit: int = 6,
) -> list[MemoryItem]:
    scoped_memories: list[MemoryItem] = []
    now = datetime.now(timezone.utc)

    agent_memories = await MemoryItem.find(
        MemoryItem.owner_type == MemoryOwnerType.AGENT,
        MemoryItem.owner_id == agent_id,
        MemoryItem.approved == True,
    ).sort(-MemoryItem.pinned, -MemoryItem.updated_at).limit(limit * 2).to_list()
    scoped_memories.extend(
        _usable_memories(
            agent_memories,
            {MemoryScope.AGENT_ONLY, MemoryScope.PUBLIC_BRANCH},
            now,
        )
    )

    if channel_id is not None:
        remaining = max(0, limit - len(scoped_memories))
        channel_memories = await MemoryItem.find(
            MemoryItem.owner_type == MemoryOwnerType.CHANNEL,
            MemoryItem.owner_id == channel_id,
            MemoryItem.approved == True,
        ).sort(-MemoryItem.pinned, -MemoryItem.updated_at).limit(max(remaining * 2, 1)).to_list()
        scoped_memories.extend(
            _usable_memories(
                channel_memories,
                {MemoryScope.CHANNEL, MemoryScope.PUBLIC_BRANCH},
                now,
            )
        )

    return scoped_memories[:limit]
