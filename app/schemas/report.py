# app/schemas/report.py

from datetime import datetime
from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    targetType: str = Field(..., description="신고 대상 분류 (예: chat_message, archive_post, archive_answer, user 등)")
    targetId: str = Field(..., description="신고할 대상의 ID입니다.")
    reason: str = Field(..., description="신고 사유의 간략한 카테고리")
    details: str = Field(default="", description="상세한 신고 내용이나 맥락")


class ReportResponse(BaseModel):
    id: str
    reporterId: str
    targetType: str
    targetId: str
    reason: str
    status: str
    createdAt: datetime
