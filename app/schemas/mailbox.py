# app/schemas/mailbox.py

from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class MailRewardResponse(BaseModel):
    exp: int
    gold: int
    trust: int
    stamina: int


class MailResponse(BaseModel):
    id: str
    type: str
    title: str
    content: str
    isRead: bool
    referenceId: Optional[str] = None
    reward: MailRewardResponse
    createdAt: datetime
    expiresAt: Optional[datetime]


class MailboxListResponse(BaseModel):
    mails: list[MailResponse]
    totalCount: int


class MailReadResponse(BaseModel):
    success: bool
    message: str
    receivedRewards: MailRewardResponse
