# app/api/v1/endpoints/billing.py

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.core.security import CurrentUser
import uuid

router = APIRouter()

class GemChargeRequest(BaseModel):
    amount: int  # 결제 금액 (원화 등)
    payment_method: str  # card, trans, vbank 등
    gems: int  # 충전할 젬 수량

class GemChargeResponse(BaseModel):
    success: bool
    transaction_id: str
    gems: int
    new_balance: int

@router.post("/billing/charge", response_model=GemChargeResponse, summary="젬 PG 결제 및 충전")
async def charge_gems(request: GemChargeRequest, current_user: CurrentUser):
    if request.amount <= 0 or request.gems <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="유효하지 않은 결제 요청입니다."
        )
    
    tx_id = f"tx_{uuid.uuid4().hex[:12]}"
    
    # Mock database update logic:
    # Under real circumstances, this would add gems to the current_user's ledger in MongoDB.
    # Since it's a simulated billing flow, we return success and the updated mock ledger state.
    
    return GemChargeResponse(
        success=True,
        transaction_id=tx_id,
        gems=request.gems,
        new_balance=1250 + request.gems
    )
