# app/models/subscription.py

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from beanie import Document
from pydantic import Field

class SubscriptionEvent(Document):
    """Lemon Squeezy 구독 이벤트 기록"""
    event_name: str                 # subscription_created, subscription_updated, etc.
    lemonsqueezy_id: str            # Lemon Squeezy측 ID
    order_id: Optional[int] = None
    customer_id: Optional[int] = None
    subscription_id: Optional[int] = None
    variant_id: Optional[int] = None
    status: str                     # active, on_trial, cancelled, expired
    renews_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    uid: str                        # 가입자 UID (Firebase UID)
    
    raw_data: Dict[str, Any]        # Webhook 전체 데이터 (디버깅용)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "subscription_events"
        indexes = ["uid", "lemonsqueezy_id", "subscription_id"]
