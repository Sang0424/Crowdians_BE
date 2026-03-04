# app/api/v1/endpoints/academy.py

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.academy import (
    KnowledgeCardResponse,
    CardSubmitRequest,
    CardSubmitResponse,
    CardRejectResponse,
    TicketRechargeResponse,
)
from app.services.academy_service import (
    get_daily_cards,
    submit_card_answer,
    reject_card_answer,
    recharge_ticket,
)

router = APIRouter()


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
    ticketIndex: int = Query(default=1, ge=1, description="몇 번째 티켓(카드)을 요청하는지 인덱스"),
    current_user: User = Depends(get_current_user),
):
    # 실제 프로덕션에서는 ticketIndex나 유저의 오늘 진행도에 따라 카드를 계산합니다.
    cards = await get_daily_cards(current_user, ticketIndex)
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
    current_user: User = Depends(get_current_user),
):
    try:
        result = await submit_card_answer(current_user, card_id, request.answer)
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
    current_user: User = Depends(get_current_user),
):
    try:
        result = await reject_card_answer(current_user, card_id)
        return CardRejectResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ══════════════════════════════════════
# POST /academy/tickets/recharge — 광고 시청으로 티켓 충전
# ══════════════════════════════════════

@router.post(
    "/academy/tickets/recharge",
    response_model=TicketRechargeResponse,
    summary="아카데미 티켓 광고 충전",
    description="티켓을 다 소진한 후 광고를 보고 추가로 충전합니다. (하루 최대 5번)",
)
async def recharge_academy_ticket(
    current_user: User = Depends(get_current_user),
):
    try:
        result = await recharge_ticket(current_user)
        return TicketRechargeResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
