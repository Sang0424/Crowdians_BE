# app/models/interaction.py
"""유저의 좋아요/스크랩 인터랙션 기록"""

import uuid
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field

INTERACTION_LIKE = "like"
INTERACTION_SCRAP = "scrap"


class UserInteraction(Document):
    """
    유저-브랜치 인터랙션 기록 (좋아요 / 스크랩).
    uid + conversation_id + branch_id + interaction_type 복합 유니크.
    """
    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uid: str                        # Firebase UID
    conversation_id: str
    branch_id: str
    interaction_type: str           # "like" | "scrap"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "user_interactions"
