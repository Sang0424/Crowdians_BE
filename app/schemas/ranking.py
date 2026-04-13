# app/schemas/ranking.py

from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.user import UserStatsResponse, CharacterResponse


class RankingUserResponse(BaseModel):
    userId: str
    nickname: str
    character: Optional[CharacterResponse] = None
    stats: UserStatsResponse


class RankingListResponse(BaseModel):
    rankings: list[RankingUserResponse]
    type: str = Field(..., description="조회된 랭킹 타입 (예: exp, trust, gold)")
