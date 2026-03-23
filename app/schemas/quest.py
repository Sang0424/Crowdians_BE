# app/schemas/quest.py

from datetime import datetime
from pydantic import BaseModel, Field


class QuestCreate(BaseModel):
    title: str = Field(..., description="의뢰 제목")
    description: str = Field(..., description="의뢰 내용")
    tags: list[str] = Field(default_factory=list, description="태그 목록")
    reward: int = Field(default=0, description="보상 골드")
    is_sos: bool = Field(default=False, description="SOS 여부")


class QuestAuthorResponse(BaseModel):
    id: str
    nickname: str
    level: int
    characterType: str


class QuestResponse(BaseModel):
    id: str
    title: str
    description: str
    tags: list[str]
    reward: int
    is_sos: bool
    author: QuestAuthorResponse
    answerCount: int
    bookmarkCount: int
    isBookmarked: bool = False
    createdAt: datetime


class QuestBookmarkToggleResponse(BaseModel):
    success: bool
    isBookmarked: bool
    message: str


class QuestCreateResponse(BaseModel):
    success: bool
    questId: str
    message: str
