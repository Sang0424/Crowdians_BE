# app/schemas/ranking.py

from pydantic import BaseModel, Field
from app.schemas.user import UserStatsResponse


class RankingUserResponse(BaseModel):
    userId: str
    nickname: str
    profileImage: str
    stats: UserStatsResponse


class RankingListResponse(BaseModel):
    rankings: list[RankingUserResponse]
    type: str = Field(..., description="조회된 랭킹 타입 (예: exp, trust, gold)")
