import uuid
from datetime import datetime, timezone
from enum import StrEnum

from beanie import Document
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryOwnerType(StrEnum):
    USER = "user"
    AGENT = "agent"
    CHANNEL = "channel"


class MemoryScope(StrEnum):
    PRIVATE = "private"
    AGENT_ONLY = "agent_only"
    CHANNEL = "channel"
    PUBLIC_BRANCH = "public_branch"


class MemoryKind(StrEnum):
    USER_PREFERENCE = "user_preference"
    AGENT_RELATIONSHIP = "agent_relationship"
    CHANNEL_LORE = "channel_lore"
    BOUNDARY = "boundary"
    UNRESOLVED_GOAL = "unresolved_goal"
    SAFETY_EVENT = "safety_event"


class MemorySource(BaseModel):
    channel_id: str
    branch_id: str
    message_ids: list[str] = Field(default_factory=list)


class MemoryItem(Document):
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    owner_type: MemoryOwnerType
    owner_id: str
    kind: MemoryKind
    scope: MemoryScope = MemoryScope.PRIVATE
    summary: str
    source: MemorySource
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    approved: bool = False
    pinned: bool = False
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    class Settings:
        name = "memories"
