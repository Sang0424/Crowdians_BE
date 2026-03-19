# app/api/v1/endpoints/rankings.py

from fastapi import APIRouter, Query

from app.schemas.ranking import RankingListResponse, RankingUserResponse
from app.schemas.user import UserStatsResponse
from app.services.ranking_service import get_top_rankings_by_type

router = APIRouter()


@router.get(
    "/rankings",
    response_model=RankingListResponse,
    summary="카테고리별 유저 랭킹 조회",
    description="type에 따라 경험치, 신뢰도 기준 등으로 소팅된 랭커 목록을 반환합니다.",
)
async def list_rankings(
    type: str = Query("exp", description="랭킹 기준 키 (exp, trust, gold, courage)"),
    limit: int = Query(50, ge=1, le=100, description="조회 갯수")
):
    try:
        top_users = await get_top_rankings_by_type(type, limit)
        
        ranking_list = []
        for u in top_users:
            stats_resp = UserStatsResponse(
                level=u.stats.level,
                exp=u.stats.exp,
                maxExp=u.stats.max_exp,
                trust=u.stats.trust,
                courage=u.stats.courage,
                stamina=u.stats.stamina,
                maxStamina=u.stats.max_stamina,
                gold=u.stats.gold,
                learningTickets=u.stats.learning_tickets,
            )
            
            ranking_list.append(
                RankingUserResponse(
                    userId=u.uid,
                    nickname=u.nickname,
                    stats=stats_resp,
                )
            )
            
        return RankingListResponse(
            rankings=ranking_list,
            type=type
        )
        
    except ValueError as e:
        return RankingListResponse(rankings=[], type=type)
