# app/models/archive.py

from datetime import datetime, timezone

from enum import Enum
from beanie import Document
from pydantic import BaseModel, Field, field_validator


class DomainCategory(str, Enum):
    ADVICE = "고민/상담"
    EMPATHY = "위로/공감"
    JOY = "기쁨/축하"
    DAILY = "일상/소통"
    RELATIONSHIP = "관계/갈등"
    CURIOSITY = "질문/호기심"
    ETC = "기타"


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

    @field_validator("domain_category", mode="before")
    @classmethod
    def validate_domain_category(cls, v):
        if isinstance(v, str):
            # 1. 값(Value)으로 매칭 시도 (예: "고민/상담")
            for member in DomainCategory:
                if member.value == v:
                    return member
            # 2. 이름(Name)으로 매칭 시도 (예: "CURIOSITY" or "curiosity")
            try:
                return DomainCategory[v.upper()]
            except KeyError:
                pass
            # 3. 매칭 실패 시 기본값
            return DomainCategory.ETC
        return v

    is_valid_question: bool | None = Field(default=None, description="유효한 질문 여부 (None: 미분류, True: 유효, False: 무효)")
    context_start_index: int = Field(default=0, description="관련 대화 시작 인덱스")
    chat_context: list[ConversationSnapshot] = Field(
        default_factory=list, 
        description="관련 대화 내역 (비공개, DB 전용)"
    )
    detailed_content: str = Field(default="", description="상세 본문 (AI 시점의 커뮤니티 요청형 문구)")
    
    source: str | None = Field(default=None, description="데이터 출처 (예: 'huggingface')")
    
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
    is_golden: bool = False                     # [추가] 골든 배지 부여 여부
    
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "archive_answers"
