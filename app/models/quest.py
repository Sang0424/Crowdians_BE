# app/models/quest.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field


class Quest(Document):
    """의뢰(Quest) 정보"""
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    reward: int = 0
    is_sos: bool = False
    author_id: str                              # 글 작성자 User uid
    
    answer_count: int = 0
    bookmark_count: int = 0

    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "quests"


class UserQuestBookmark(Document):
    """사용자의 의뢰 북마크 매핑 테이블"""
    user_id: str                                # User uid
    quest_id: str                               # Quest _id (string)
    
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "user_quest_bookmarks"
        indexes = [
            [("user_id", 1), ("quest_id", 1)]   # 유니크 복합 인덱스 (선택 사항이나 보통 필요)
        ]
