# app/models/interaction.py
"""유저의 좋아요/스크랩 인터랙션 기록"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field

INTERACTION_LIKE = "like"
INTERACTION_SCRAP = "scrap"
INTERACTION_UPVOTE = "upvote"
INTERACTION_DOWNVOTE = "downvote"


class UserInteraction(Document):
    """
    유저-브랜치/메시지 인터랙션 기록 (좋아요 / 스크랩 / 추천 / 비추천).
    """
    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uid: str                        # OAuth UID
    channel_id: str
    branch_id: str
    message_id: Optional[str] = None # 메시지 관련 인터랙션(추천/비추천)일 경우 설정
    interaction_type: str           # "like" | "scrap" | "upvote" | "downvote"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "user_interactions"
