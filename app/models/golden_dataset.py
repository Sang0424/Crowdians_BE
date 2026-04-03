# app/models/golden_dataset.py
from datetime import datetime, timezone
from beanie import Document
from pydantic import Field

class GoldenDataset(Document):
    """B2B 판매용 A/B 테스트 기반 RLHF 선호도 데이터셋 (정제 완료)"""
    
    raw_prompt: str = Field(description="유저 질문 원본")
    original_ai_answer: str = Field(description="AI의 오답 원본")
    
    # [핵심] 승률 기반으로 순위가 매겨진 답변 리스트 (허니팟 제외)
    # 예: [{"answer": "A답변", "wins": 10, "matches": 12, "win_rate": 0.83, "rank": 1}, ...]
    ranked_answers: list[dict] = Field(default_factory=list)
    
    domain_category: str = Field(description="데이터 도메인 카테고리")
    tags: list[str] = Field(default_factory=list)
    chat_context: list[dict] = Field(default_factory=list, description="원본 대화 내역 스냅샷 (RLHF 학습용)")
    
    total_matches_played: int = Field(description="이 질문에서 이루어진 총 A/B 테스트 횟수")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "golden_datasets"
