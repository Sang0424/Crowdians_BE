# app/schemas/archive.py

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


# ── 답변 스키마 ──

class AuthorResponse(BaseModel):
    id: str
    nickname: str
    trustCount: int
    level: int
    characterType: str


class ArchiveAnswerResponse(BaseModel):
    id: str                 # answer document _id
    postId: str
    author: AuthorResponse
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
    title: str
    content: str
    isSos: bool
    category: str
    bounty: int
    author: AuthorResponse
    answerCount: int
    targetUserId: Optional[str] = None
    status: str = "open"
    createdAt: datetime
    characterType: str
    isBookmarked: bool = False
    isDirectCommission: bool = False
    tags: list[str] = []         # LLM 추출 태그
    summary: Optional[str] = None # LLM 3줄 요약


class ArchivePostDetailResponse(ArchivePostResponse):
    """상세 조회 시 하위 답변들을 포함"""
    answers: list[ArchiveAnswerResponse]


class ArchivePostRequest(BaseModel):
    """(선택) 직접 질문을 작성하는 경우"""
    title: str = Field(..., description="질문 제목")
    content: str = Field(..., description="질문 내용")
    category: str = Field(default="general")
    targetUserId: Optional[str] = Field(default=None, description="직접 의뢰할 대상의 UID")
    bounty: int = Field(default=0, description="걸고 싶은 골드 바운티")
    locale: str = Field(default="ko", description="언어 설정")


class ArchiveBookmarkResponse(BaseModel):
    success: bool
    isBookmarked: bool


class PaginatedArchiveResponse(BaseModel):
    """페이지네이션 래퍼"""
    items: list[ArchivePostResponse]
    page: int
    size: int
    totalCount: int
    hasMore: bool


class ArchivePostSubmitResponse(BaseModel):
    success: bool
    postId: str
    message: str

class ArchiveUpdateRequest(BaseModel):
    title: str | None = Field(default=None, description="수정할 제목 (게시글 전용, 답변 수정 시 생략 가능)")
    content: str = Field(..., description="수정할 내용")


class BasicActionResponse(BaseModel):
    success: bool
    message: str


# ── 투표 스키마 ──

class TrustVoteResponse(BaseModel):
    success: bool
    isTrusted: bool         # 토글 후 현재 상태
    trustCount: int         # 업데이트된 투표수
    message: str
