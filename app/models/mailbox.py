# app/models/mailbox.py

from datetime import datetime, timezone
from beanie import Document
from pydantic import BaseModel, Field
from typing import Optional


class MailReward(BaseModel):
    """우편에 동봉된 보상"""
    exp: int = 0
    gold: int = 0
    trust: int = 0
    stamina: int = 0


class Mail(Document):
    """우편함(Mailbox) 데이터모델"""
    user_id: str                    # 수신자 UID
    type: str                       # "system", "academy_result", "sos_reply" 등
    title: str                      # 우편 제목
    content: str                    # 우편 내용
    
    is_read: bool = False           # 읽음 & 보상 수령 여부
    reference_id: str | None = None  # 해당 우편이 연결된 ArchivePost의 ID
    reward: MailReward = Field(default_factory=MailReward)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None  # 만료 기한이 있을 경우

    class Settings:
        name = "mails"
