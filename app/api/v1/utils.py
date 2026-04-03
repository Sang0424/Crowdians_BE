# app/api/v1/utils.py
# 여러 엔드포인트에서 공통으로 사용하는 변환 유틸리티

from app.models.user import User
from app.schemas.auth import (
    UserResponse,
    UserStatsResponse,
    CharacterResponse,
    EquippedPartsResponse,
)


def user_to_response(user: User) -> UserResponse:
    """DB User 모델을 프론트엔드 호환 UserResponse로 변환"""
    return UserResponse(
        uid=user.uid,
        email=user.email,
        nickname=user.nickname,
        stats=UserStatsResponse(
            level=user.stats.level,
            exp=user.stats.exp,
            maxExp=user.stats.max_exp,
            gold=user.stats.gold,
            stamina=user.stats.stamina,
            maxStamina=user.stats.max_stamina,
            trust=user.stats.trust,
            intelligence=user.stats.intelligence,
            courage=user.stats.courage,
            intimacy=user.stats.intimacy,
            dailyChatExp=user.stats.daily_chat_exp,
            dailyPetCount=user.stats.daily_pet_count,
            dailySosCount=user.stats.daily_sos_count,
            dailyCommissionCount=user.stats.daily_commission_count,
            isOnboardingDone=user.stats.is_onboarding_done,
            learningTickets=user.stats.learning_tickets,
            maxLearningTickets=user.stats.max_learning_tickets,
        ),
        character=CharacterResponse(
            type=user.character.type,
            equippedParts=EquippedPartsResponse(
                head=user.character.equipped_parts.head,
                hand=user.character.equipped_parts.hand,
                body=user.character.equipped_parts.body,
                effect=user.character.equipped_parts.effect,
            ),
            unlockedParts=user.character.unlocked_parts,
        ),
        createdAt=user.created_at,
        lastLoginAt=user.last_login_at,
    )
