# app/models/academy.py

from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class KnowledgeCard(Document):
    """지식 카드 (Academy 문제)"""
    type: str = "vote"              # "vote" (A/B 선택), "teach" (주관식 또는 상식), "quiz"
    question: str                   # 질문 제목 또는 요약
    content: str | None = None      # 질문 상세 내용
    summary: str | None = None      # 질문 요약 (ArchivePost 연동 시 복사)
    locale: str = Field(default="ko", description="언어 설정")
    choices: list[str] = Field(default_factory=list)
    correct_answer: str | int = ""  # 정답 (번호일 수도 있고 텍스트일 수도 있음)
    honeypot_answer: str = Field(default="", description="매크로/어뷰징 유저를 걸러내기 위한 함정 오답")
    trust_count: int = 0            # 투표 수/신뢰도 (10 이상 시 골든 데이터셋 편입 등)
    priority: int = 0               # 큐에서의 노출 우선순위 (SOS 게시글 등)

    # 🌟 [추가] 마이그레이션 및 A/B 테스트 통계 필드
    is_migrated: bool = Field(default=False, description="골든 데이터셋으로 추출 완료되었는지 여부")
    total_matches: int = 0          # 총 A/B 매치 진행 횟수
    choice_wins: dict[str, int] = Field(default_factory=dict, description="답변별 가중 승리 횟수")
    choice_matches: dict[str, int] = Field(default_factory=dict, description="답변별 노출(매치) 횟수")
    choice_answer_ids: dict[str, str] = Field(default_factory=dict, description="선택지 텍스트 -> ArchiveAnswer ID 매핑 (신뢰도 투표 연동용)")
    
    # RLHF나 특정 출처가 있다면 기록
    source_message_id: str | None = None
    linked_post_id: str | None = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "knowledge_cards"


class CardResponse(Document):
    """유저가 카드에 응답한 기록"""
    user_id: str                    # User.uid
    card_id: str                    # KnowledgeCard.id (문자열 변환)
    answer: str | int               # 유저가 선택하거나 작성한 답
    is_correct: bool = False
    is_rejected: bool = False     # "둘 다 별로"를 선택한 경우 True
    reward_exp: int = 0
    reward_gold: int = 0
    reward_trust: int = 0
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "card_responses"
