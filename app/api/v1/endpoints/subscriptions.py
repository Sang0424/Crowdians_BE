# app/api/v1/endpoints/subscriptions.py

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.responses import JSONResponse

from app.core.security import get_current_user
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.schemas.subscription import SubscriptionStatusResponse, CheckoutURLResponse, CustomerPortalResponse

router = APIRouter()

@router.post(
    "/checkout",
    response_model=CheckoutURLResponse,
    summary="구독 결제 URL 생성",
    description="Lemon Squeezy 결제 페이지로 이동할 수 있는 URL을 생성합니다."
)
async def create_checkout(current_user: User = Depends(get_current_user)):
    url = await SubscriptionService.create_checkout_url(current_user)
    return CheckoutURLResponse(checkoutUrl=url)

@router.post(
    "/webhook",
    summary="Lemon Squeezy Webhook 수신",
    description="결제 성공, 구독 갱신, 취소 등의 이벤트를 수신하여 처리합니다."
)
async def lemonsqueezy_webhook(request: Request):
    # 1. 서명 검증
    if not await SubscriptionService.verify_webhook(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    # 2. 페이로드 파싱
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
        
    # 3. 이벤트 처리 (Background Task로 돌려도 좋지만 일단 직접 처리)
    await SubscriptionService.handle_webhook(payload)
    
    return {"status": "success"}

@router.get(
    "/me",
    response_model=SubscriptionStatusResponse,
    summary="현재 구독 상태 조회",
    description="로그인한 유저의 현재 구독 플랜 및 일일 잔여 횟수를 조회합니다."
)
async def get_subscription_status(current_user: User = Depends(get_current_user)):
    is_premium = current_user.subscription_plan == "premium"
    
    # 남은 횟수 계산 (무료 기준 3회, 1회)
    sos_limit = 999 if is_premium else 3
    commission_limit = 999 if is_premium else 1
    
    return SubscriptionStatusResponse(
        plan=current_user.subscription_plan,
        expiresAt=current_user.subscription_expires_at,
        isPremium=is_premium,
        dailySosRemaining=max(0, sos_limit - current_user.stats.daily_sos_count),
        dailyCommissionRemaining=max(0, commission_limit - current_user.stats.daily_commission_count)
    )

@router.get(
    "/portal",
    response_model=CustomerPortalResponse,
    summary="구독 관리 포털 URL 조회",
    description="로그인한 유저가 구독을 관리할 수 있는 Lemon Squeezy 포털 페이지(Signed URL)를 조회합니다."
)
async def get_portal_url(current_user: User = Depends(get_current_user)):
    url = await SubscriptionService.get_customer_portal_url(current_user)
    return CustomerPortalResponse(portalUrl=url)
