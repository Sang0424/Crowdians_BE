# app/schemas/mailbox.py

from datetime import datetime
from pydantic import BaseModel


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
    referenceId: str | None = None
    reward: MailRewardResponse
    createdAt: datetime
    expiresAt: datetime | None


class MailboxListResponse(BaseModel):
    mails: list[MailResponse]
    totalCount: int


class MailReadResponse(BaseModel):
    success: bool
    message: str
    receivedRewards: MailRewardResponse
