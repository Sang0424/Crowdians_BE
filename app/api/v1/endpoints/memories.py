from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.security import CurrentUser
from app.models.channel import Channel
from app.models.memory import MemoryItem, MemoryKind, MemoryOwnerType, MemoryScope
from app.services.prompt_guard_service import (
    PromptInjectionBlockedError,
    PromptSurface,
    require_safe_prompt_text,
)

router = APIRouter(prefix="/memories", tags=["Memories"])


class MemoryOut(BaseModel):
    memory_id: str
    owner_type: MemoryOwnerType
    owner_id: str
    kind: MemoryKind
    scope: MemoryScope
    summary: str
    confidence: float
    approved: bool
    pinned: bool
    source_channel_id: str
    source_branch_id: str
    source_message_ids: list[str]
    created_at: datetime
    updated_at: datetime


class UpdateMemoryRequest(BaseModel):
    summary: str | None = None
    scope: MemoryScope | None = None
    approved: bool | None = None
    pinned: bool | None = None


def _memory_to_out(memory: MemoryItem) -> MemoryOut:
    return MemoryOut(
        memory_id=memory.memory_id,
        owner_type=memory.owner_type,
        owner_id=memory.owner_id,
        kind=memory.kind,
        scope=memory.scope,
        summary=memory.summary,
        confidence=memory.confidence,
        approved=memory.approved,
        pinned=memory.pinned,
        source_channel_id=memory.source.channel_id,
        source_branch_id=memory.source.branch_id,
        source_message_ids=memory.source.message_ids,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


async def _ensure_memory_owner(memory: MemoryItem, uid: str) -> None:
    if memory.owner_type == MemoryOwnerType.USER and memory.owner_id == uid:
        return

    if memory.owner_type == MemoryOwnerType.CHANNEL:
        channel = await Channel.get(memory.owner_id)
        if channel is not None and channel.creator_uid == uid:
            return

    raise HTTPException(status_code=403, detail="이 기억을 수정할 권한이 없습니다.")


@router.get("", response_model=list[MemoryOut], summary="내가 관리할 수 있는 기억 조회")
async def list_memories(
    current_user: CurrentUser,
    channel_id: str | None = Query(None),
    approved: bool | None = Query(None),
):
    query = MemoryItem.find()
    if channel_id is not None:
        channel = await Channel.get(channel_id)
        if channel is None:
            raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
        if channel.creator_uid != current_user.uid:
            raise HTTPException(status_code=403, detail="이 채널의 기억을 조회할 권한이 없습니다.")
        query = query.find(
            MemoryItem.owner_type == MemoryOwnerType.CHANNEL,
            MemoryItem.owner_id == channel_id,
        )
    else:
        query = query.find(
            MemoryItem.owner_type == MemoryOwnerType.USER,
            MemoryItem.owner_id == current_user.uid,
        )

    if approved is not None:
        query = query.find(MemoryItem.approved == approved)

    memories = await query.sort(-MemoryItem.pinned, -MemoryItem.updated_at).to_list()
    return [_memory_to_out(memory) for memory in memories]


@router.patch("/{memory_id}", response_model=MemoryOut, summary="기억 승인/수정")
async def update_memory(
    memory_id: str,
    body: UpdateMemoryRequest,
    current_user: CurrentUser,
):
    memory = await MemoryItem.find_one(MemoryItem.memory_id == memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="기억을 찾을 수 없습니다.")

    await _ensure_memory_owner(memory, current_user.uid)

    if body.summary is not None:
        try:
            require_safe_prompt_text(PromptSurface.MEMORY_SUMMARY, body.summary)
        except PromptInjectionBlockedError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        memory.summary = body.summary
    if body.approved is True:
        try:
            require_safe_prompt_text(PromptSurface.MEMORY_SUMMARY, memory.summary)
        except PromptInjectionBlockedError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if body.scope is not None:
        memory.scope = body.scope
    if body.approved is not None:
        memory.approved = body.approved
    if body.pinned is not None:
        memory.pinned = body.pinned

    await memory.save()
    return _memory_to_out(memory)


@router.delete("/{memory_id}", status_code=204, summary="기억 삭제")
async def delete_memory(memory_id: str, current_user: CurrentUser) -> None:
    memory = await MemoryItem.find_one(MemoryItem.memory_id == memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="기억을 찾을 수 없습니다.")

    await _ensure_memory_owner(memory, current_user.uid)
    await memory.delete()
