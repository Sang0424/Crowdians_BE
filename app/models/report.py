# app/models/report.py

from datetime import datetime, timezone
from beanie import Document
from pydantic import Field


class Report(Document):
    """신고 (AI 답변 이상, 부적절한 유저 게시글 등)"""
    reporter_id: str                # 신고자 UID
    
    target_type: str                # "chat_message", "archive_post", "archive_answer", "user" 등
    target_id: str                  # 신고 대상의 ID
    
    reason: str                     # 신고 사유
    details: str = ""               # 상세 설명
    
    status: str = "pending"         # "pending", "reviewed", "rejected", "resolved"
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None

    class Settings:
        name = "reports"
