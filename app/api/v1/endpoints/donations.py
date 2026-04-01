# app/api/v1/endpoints/donations.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import CurrentUser
from app.schemas.donation import (
    KofiWebhookData, 
    DonationResponse, 
    UserDonationStatus
)
from app.services.donation_service import DonationService

router = APIRouter()


@router.post(
    "/donations/kofi/webhook",
    status_code=status.HTTP_200_OK,
    summary="Ko-fi Webhook 수신",
    description="Ko-fi로부터 후원 웹훅을 수신하고 칭호를 업데이트합니다."
)
async def kofi_webhook(data: KofiWebhookData):
    success = await DonationService.process_kofi_webhook(data)
    if not success:
        # 토큰 불일치 등의 경우 403 반환
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid verification token"
        )
    return {"status": "success"}


@router.get(
    "/donations/me",
    response_model=List[DonationResponse],
    summary="내 후원 내역 조회",
    description="로그인한 유저의 전체 후원 내역을 조회합니다."
)
async def get_my_donations(current_user: CurrentUser):
    donations = await DonationService.get_my_donations(current_user.uid)
    return donations


@router.get(
    "/donations/status",
    response_model=UserDonationStatus,
    summary="내 후원 상태 및 칭호 조회",
    description="현재 후원 등급, 누적 금액, 해금된 칭호 목록을 조회합니다."
)
async def get_donation_status(current_user: CurrentUser):
    return UserDonationStatus(
        donation_tier=current_user.donation_tier,
        total_donated=current_user.total_donated,
        available_titles=current_user.available_titles,
        current_title=current_user.stats.title
    )
