# app/api/v1/endpoints/feed.py
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.models.conversation import Conversation, Branch
from app.models.interaction import UserInteraction, INTERACTION_LIKE

router = APIRouter(prefix="/feed", tags=["Feed"])

class FeedBranchItem(BaseModel):
    conversation_id: str
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
    (실제 구현에서는 Beanie의 Aggregation 파이프라인이나 복잡한 쿼리를 사용해야 하지만,
     여기서는 구조적 뼈대를 제공합니다.)
    """
    # 임시 목업 데이터 생성 로직 대신 DB 쿼리라고 가정.
    # Beanie를 사용할 경우 Conversation 안의 branches를 필터링하는 쿼리가 필요함.
    # 예시 로직:
    # conversations = await Conversation.find(Conversation.is_public == True).to_list()
    # (추출된 브랜치들을 engagement_score로 정렬 후 페이징)
    
    return []

@router.post("/{conversation_id}/{branch_id}/like")
async def like_branch(conversation_id: str, branch_id: str):
    """
    특정 브랜치에 좋아요(인터랙션) 기록 및 점수 업데이트.
    """
    # 1. UserInteraction 문서 생성 (uid는 로그인한 유저, 여기선 생략)
    # 2. Conversation 내부의 Branch.likes 증가 및 engagement_score 재계산
    
    return {"status": "success", "message": "Liked branch"}
