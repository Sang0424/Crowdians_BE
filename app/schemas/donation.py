# app/schemas/donation.py

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class KofiWebhookData(BaseModel):
    """Ko-fi Webhook Payload Data"""
    message_id: str
    timestamp: datetime
    type: str                        # "Donation" | "Subscription" | "Shop Order"
    from_name: str
    message: Optional[str] = ""
    amount: str                      # "1.00"
    currency: str                    # "USD"
    url: str
    email: str
    is_public: bool
    kofi_transaction_id: str
    verification_token: str
    shop_items: Optional[List[dict]] = None
    tier_name: Optional[str] = None


class DonationResponse(BaseModel):
    """후원 내역 응답"""
    id: str
    platform: str
    amount: float
    currency: str
    donor_name: str
    message: str
    verified_at: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserDonationStatus(BaseModel):
    """유저의 현재 후원 상태 및 해금된 칭호"""
    donation_tier: str
    total_donated: float
    available_titles: List[str]
    current_title: Optional[str] = None


class TitleUpdate(BaseModel):
    """칭호 변경 요청"""
    title: str
