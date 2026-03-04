# app/models/chat.py

from datetime import datetime, timezone

from beanie import Document
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """채팅 메시지 (임베디드 모델)"""
    role: str                       # "user" | "model"
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatConversation(Document):
    """유저와 AI(Pico) 간의 대화 세션을 저장하는 Document"""
    uid: str                        # User의 uid
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_conversations"
