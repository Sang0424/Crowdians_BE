# app/schemas/subscription.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class SubscriptionStatusResponse(BaseModel):
    plan: str                       # 'free' | 'premium'
    expiresAt: Optional[datetime]
    isPremium: bool
    dailySosRemaining: int
    dailyCommissionRemaining: int

class CheckoutURLResponse(BaseModel):
    checkoutUrl: str

class CancelSubscriptionRequest(BaseModel):
    reason: Optional[str] = None
