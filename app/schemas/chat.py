# app/schemas/chat.py

from datetime import datetime
from pydantic import BaseModel, Field


# ── 채팅 메시지 ──

class ChatMessageRequest(BaseModel):
    content: str = Field(..., description="유저의 채팅 메시지")


class ChatMessageResponse(BaseModel):
    role: str = Field(..., description="user | model")
    content: str = Field(..., description="메시지 내용")
    createdAt: datetime


class ChatSendResponse(BaseModel):
    """메시지 전송 성공 응답 (스탯 변화량 포함)"""
    userMessage: ChatMessageResponse
    aiMessage: ChatMessageResponse
    expGained: int = 0
    staminaConsumed: int = 0
    intimacyGained: int = 0
    requiresLogin: bool = False


# ── 채팅 내역 ──

class ChatHistoryResponse(BaseModel):
    conversationId: str
    messages: list[ChatMessageResponse]


# ── 마음에 들지 않는 답변 신고 ──

class ChatUnlikeRequest(BaseModel):
    messageIndex: int = Field(..., description="배열 상의 메시지 인덱스")
    reason: str = Field(default="", description="신고 이유")


class ChatUnlikeResponse(BaseModel):
    success: bool
    message: str


# ── 지식 의뢰 (SOS) ──

class ChatSosRequest(BaseModel):
    question: str = Field(..., description="아카데미에 의뢰할 질문")


class ChatSosResponse(BaseModel):
    success: bool
    goldConsumed: int
    message: str
