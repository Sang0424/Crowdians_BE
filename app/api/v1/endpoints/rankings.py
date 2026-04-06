# app/api/v1/endpoints/rankings.py

from fastapi import APIRouter, Query
import logging # 로그 확인용

from app.schemas.ranking import RankingListResponse, RankingUserResponse
from app.schemas.user import UserStatsResponse, CharacterResponse, EquippedPartsResponse
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
                intelligence=u.stats.intelligence,
                intimacy=u.stats.intimacy,
                dailyChatExp=u.stats.daily_chat_exp,
                dailyPetCount=u.stats.daily_pet_count,
                dailySosCount=u.stats.daily_sos_count,
                dailyCommissionCount=u.stats.daily_commission_count,
                isOnboardingDone=u.stats.is_onboarding_done,
                maxLearningTickets=u.max_learning_tickets,
            )

            equipped_parts_resp = None
            if u.character and u.character.equipped_parts:
                equipped_parts_resp = EquippedPartsResponse(
                    head=u.character.equipped_parts.head,
                    hand=u.character.equipped_parts.hand,
                    body=u.character.equipped_parts.body,
                    effect=u.character.equipped_parts.effect,
                )
            
            char_resp = None
            if u.character:
                char_resp = CharacterResponse(
                    type=u.character.type,
                    equippedParts=equipped_parts_resp,          # 카멜 케이스 적용 완료
                    unlockedParts=u.character.unlocked_parts or [], # 카멜 케이스 적용 완료
                )
            
            ranking_list.append(
                RankingUserResponse(
                    userId=u.uid,
                    nickname=u.nickname,
                    stats=stats_resp,
                    character=char_resp
                )
            )
            
        return RankingListResponse(
            rankings=ranking_list,
            type=type
        )
        
    except ValueError as e:
        logging.error(f"Ranking error: {e}") # 에러를 터미널에 출력
        return RankingListResponse(rankings=[], type=type)
