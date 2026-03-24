# app/models/archive.py

from datetime import datetime, timezone

from beanie import Document
from pydantic import BaseModel, Field


class ArchiveAnswer(BaseModel):
    """지식 도서관 답변 (임베디드 모델로 처리하거나 별도 Document로 처리 가능)
    여기서는 관리 편의상 ArchivePost 내부에 임베디드로 저장하는 방식을 추천합니다만,
    투표 및 독립적 관리를 위해 별도 Document로 분리할 수도 있습니다.
    api 명세에서는 /archive/answers/{answerId}/trust 가 있으므로,
    답변이 별도 ID를 갖거나, Post 내에서 식별 가능한 ID를 가져야 합니다.
    여기서는 별도 Document로 구성합니다.
    """
    pass


class ArchivePost(Document):
    """지식 도서관 질문 글"""
    title: str
    content: str
    is_sos: bool = False
    category: str = "general"
    bounty: int = 0
    target_user_id: str | None = None            # 직접 의뢰 시 대상의 UID
    status: str = "open"                        # 'open', 'commissioned', 'rejected', 'answered' 등
    author_id: str                              # 글 작성자 User uid
    locale: str = "ko"
    
    tags: list[str] = Field(default_factory=list) # LLM 추출 태그
    summary: str = ""                            # LLM 3줄 요약
    
    # 답변들의 ID 목록 (ArchiveAnswer Document의 id)
    # 또는 역방향 참조를 위해 안 들고 있어도 무방합니다. (보통 RDBMS처럼)
    # 여기서는 빠른 쿼리를 위해 답변 개수 등을 같이 들고 있을 수 있습니다.
    answer_count: int = 0
    bookmark_count: int = 0

    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "archive_posts"


class ArchiveAnswer(Document):
    """지식 도서관 답변 글"""
    post_id: str                                # 질문 글 ArchivePost 의 _id 문자열
    author_id: str                              # 작성자 User uid
    content: str
    
    trust_count: int = 0                        # "신뢰함" 받은 횟수
    voted_user_ids: list[str] = Field(default_factory=list)  # 중복 투표 방지를 위한 uid 목록
    
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "archive_answers"
