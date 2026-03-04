# app/schemas/archive.py

from datetime import datetime
from pydantic import BaseModel, Field


# ── 답변 스키마 ──

class ArchiveAnswerResponse(BaseModel):
    id: str                 # answer document _id
    postId: str
    authorId: str
    content: str
    trustCount: int
    isTrustedByMe: bool = False  # 유저 본인이 이미 투표했는지 여부
    createdAt: datetime


class ArchiveAnswerRequest(BaseModel):
    content: str = Field(..., description="답변 내용")


class ArchiveAnswerSubmitResponse(BaseModel):
    success: bool
    answerId: str
    message: str


# ── 질문 글 스키마 ──

class ArchivePostResponse(BaseModel):
    id: str                 # post document _id
    question: str
    category: str
    bounty: int
    authorId: str
    answerCount: int
    createdAt: datetime


class ArchivePostDetailResponse(ArchivePostResponse):
    """상세 조회 시 하위 답변들을 포함"""
    answers: list[ArchiveAnswerResponse]


class ArchivePostRequest(BaseModel):
    """(선택) 직접 질문을 작성하는 경우"""
    question: str = Field(..., description="질문 내용")
    category: str = Field(default="general")
    bounty: int = Field(default=0, description="걸고 싶은 골드 바운티")


class ArchivePostSubmitResponse(BaseModel):
    success: bool
    postId: str
    message: str


# ── 투표 스키마 ──

class TrustVoteResponse(BaseModel):
    success: bool
    isTrusted: bool         # 토글 후 현재 상태
    trustCount: int         # 업데이트된 투표수
    message: str
