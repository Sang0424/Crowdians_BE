# app/models/archive.py

from datetime import datetime, timezone

from enum import Enum
from beanie import Document
from pydantic import BaseModel, Field


class DomainCategory(str, Enum):
    IT_PROGRAMMING = "IT/프로그래밍"
    LAW_TAX = "법률/세무"
    SCIENCE_TECH = "과학/기술"
    DAILY_LIFE = "일상/생활"
    CREATIVE_WRITING = "창작/글쓰기"
    ETC = "기타"


class ConversationSnapshot(BaseModel):
    """Unlike/SOS 제출 시점 기준 대화 내역 스냅샷"""
    role: str      # "user" | "model"
    content: str


class ConversationSnapshot(BaseModel):
    """Unlike/SOS 제출 시점 기준 대화 내역 스냅샷"""
    role: str      # "user" | "model"
    content: str


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
    target_user_id: str | None = None            # 직접 의뢰 시 대상의 UID
    status: str = "open"                        # 'open', 'commissioned', 'rejected', 'answered' 등
    author_id: str                              # 글 작성자 User uid
    locale: str = "ko"
    
    tags: list[str] = Field(default_factory=list) # LLM 추출 태그
    summary: str = ""                            # LLM 3줄 요약
    
    # 🌟 [추가] 골든 데이터셋을 위한 원본 보존 및 메타데이터 필드
    raw_prompt: str = Field(default="", description="유저가 입력한 최초 질문 원본")
    original_ai_answer: str = Field(default="", description="불만족 평가를 받은 AI의 최초 오답 원본")
    domain_category: DomainCategory = Field(default=DomainCategory.ETC, description="데이터 판매용 대분류")
    chat_context: list[ConversationSnapshot] = Field(
        default_factory=list, 
        description="관련 대화 내역 (비공개, DB 전용)"
    )
    
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
