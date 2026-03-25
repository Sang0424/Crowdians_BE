# app/api/v1/endpoints/mailbox.py

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.security import CurrentUser
from app.models.user import User
from app.schemas.mailbox import (
    MailResponse,
    MailRewardResponse,
    MailboxListResponse,
    MailReadResponse,
)
from app.services.mailbox_service import get_user_mails, read_mail

router = APIRouter()


@router.get(
    "/mailbox",
    response_model=MailboxListResponse,
    summary="우편함 목록 조회",
    description="자신의 우편함을 최신순으로 조회합니다. (Pagination)",
)
async def list_mailbox(
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지 당 항목 수"),
):
    skip = (page - 1) * limit
    mails, total = await get_user_mails(current_user.uid, skip, limit)
    
    mail_responses = []
    for m in mails:
        mail_responses.append(
            MailResponse(
                id=str(m.id),
                type=m.type,
                title=m.title,
                content=m.content,
                isRead=m.is_read,
                referenceId=m.reference_id,
                reward=MailRewardResponse(
                    exp=m.reward.exp,
                    gold=m.reward.gold,
                    trust=m.reward.trust,
                    stamina=m.reward.stamina
                ),
                createdAt=m.created_at,
                expiresAt=m.expires_at
            )
        )
        
    return MailboxListResponse(
        mails=mail_responses,
        totalCount=total
    )


@router.put(
    "/mailbox/{mail_id}/read",
    response_model=MailReadResponse,
    summary="우편 읽음 처리 & 보상 수령",
    description="미열람 상태의 우편을 열어 동봉된 보상을 유저 스탯에 반영합니다.",
)
async def read_mailbox_mail(
    mail_id: str,
    current_user: CurrentUser,
):
    try:
        result = await read_mail(current_user, mail_id)
        return MailReadResponse(
            success=result["success"],
            message=result["message"],
            receivedRewards=MailRewardResponse(**result["receivedRewards"])
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
