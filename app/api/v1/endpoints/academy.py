# app/api/v1/endpoints/academy.py

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.security import CurrentUser
from app.models.user import User
from app.schemas.academy import (
    KnowledgeCardResponse,
    CardSubmitRequest,
    CardSubmitResponse,
    CardRejectResponse,
    StartSessionResponse
)
from app.services.academy_service import (
    get_daily_cards,
    submit_card_answer,
    reject_card_answer,
)

router = APIRouter()


# ══════════════════════════════════════
# POST /academy/start — 아카데미 세션 시작 (티켓 차감)
# ══════════════════════════════════════
@router.post(
    "/academy/start",
    response_model=StartSessionResponse,
    summary="아카데미 세션 시작 (티켓 차감)",
    description="아카데미 시작 버튼을 눌렀을 때 티켓 1장을 차감합니다.",
)
async def start_academy(current_user: CurrentUser):
    from app.services.academy_service import start_academy_session
    try:
        result = await start_academy_session(current_user)
        return StartSessionResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
# ══════════════════════════════════════
# GET /academy/cards — 학습카드 목록 조회
# ══════════════════════════════════════

@router.get(
    "/academy/cards",
    response_model=list[KnowledgeCardResponse],
    summary="지식 카드(학습카드) 목록 조회",
    description="하루 최대 5장의 지식 카드(Vote/Teach 믹스)를 조회합니다.",
)
async def get_cards(
    current_user: CurrentUser,
    ticketIndex: int = Query(default=1, description="몇 번째 티켓(카드)을 요청하는지 인덱스"),
    locale: str = Query("ko", description="언어 설정"),
):
    # 실제 프로덕션에서는 ticketIndex나 유저의 오늘 진행도에 따라 카드를 계산합니다.
    cards = await get_daily_cards(current_user, ticketIndex, locale)
    return [KnowledgeCardResponse(**card) for card in cards]


# ══════════════════════════════════════
# POST /academy/cards/{cardId}/submit — 학습카드 응답 제출
# ══════════════════════════════════════

@router.post(
    "/academy/cards/{card_id}/submit",
    response_model=CardSubmitResponse,
    summary="지식 카드 응답 제출",
    description="정답 여부를 판별하여 보상을 지급(경험치, 골드, 신뢰도 등)하고 티켓을 소모합니다.",
)
async def submit_card(
    card_id: str,
    request: CardSubmitRequest,
    current_user: CurrentUser,
):
    try:
        from app.models.academy import KnowledgeCard
        from bson import ObjectId
        from app.services.academy_service import submit_ab_vote

        # 카드 타입 확인을 위해 먼저 조회
        try:
            card = await KnowledgeCard.get(ObjectId(card_id))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 카드 ID입니다.")
            
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="카드를 찾을 수 없습니다.")

        # 1. A/B 테스트 목적의 Vote 타입인 경우 (chosen_answer가 전달된 경우)
        if card.type == "vote" and request.chosen_answer is not None:
            result = await submit_ab_vote(
                current_user, 
                card_id, 
                str(request.chosen_answer), 
                str(request.unchosen_answer or "")
            )
        else:
            # 2. Teach, Quiz 타입 또는 단일 답변인 경우
            # answer가 없으면 chosen_answer를 fallback으로 사용
            final_answer = request.answer if request.answer is not None else request.chosen_answer
            if final_answer is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="답변 데이터가 누락되었습니다.")
                
            result = await submit_card_answer(current_user, card_id, final_answer)

        return CardSubmitResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ══════════════════════════════════════
# POST /academy/cards/{cardId}/reject — 카드 답변 둘다 별로
# ══════════════════════════════════════

@router.post(
    "/academy/cards/{card_id}/reject",
    response_model=CardRejectResponse,
    summary="답변 모두 거절 (Reject)",
    description="Vote형 A/B 답변이 둘 다 마음에 들지 않을 때 거절하고 로그를 남깁니다.",
)
async def reject_card(
    card_id: str,
    current_user: CurrentUser,
):
    try:
        result = await reject_card_answer(current_user, card_id)
        return CardRejectResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
