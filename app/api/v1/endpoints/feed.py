# app/api/v1/endpoints/feed.py
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.models.channel import Channel, Branch
from app.models.interaction import UserInteraction, INTERACTION_LIKE

router = APIRouter(prefix="/feed", tags=["Feed"])

class FeedBranchItem(BaseModel):
    channel_id: str
    branch_id: str
    topic: str
    category: str
    engagement_score: float
    likes: int
    scraps: int
    message_preview: str

@router.get("", response_model=List[FeedBranchItem])
async def get_public_feed(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=50),
    skip: int = Query(0, ge=0)
):
    """
    마켓플레이스에 노출된 공개(is_public) 브랜치 피드 조회.
    engagement_score 기준으로 내림차순 정렬하여 반환합니다.
    """
    # channels = await Channel.find(Channel.is_public == True).to_list()
    return []

@router.post("/{channel_id}/{branch_id}/like")
async def like_branch(channel_id: str, branch_id: str):
    """
    특정 브랜치에 좋아요(인터랙션) 기록 및 점수 업데이트.
    """
    return {"status": "success", "message": "Liked branch"}
