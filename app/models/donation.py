# app/models/donation.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field


class Donation(Document):
    """후원 기록 (MongoDB collection: donations)"""
    user_uid: Optional[str] = None           # 연결된 유저 UID
    platform: str                            # "crypto" | "kofi"
    platform_tx_id: str                      # 플랫폼별 거래 ID (Ko-fi의 경우 verification_token이나 transaction_id)
    donor_name: str                          # 후원자 이름
    donor_email: Optional[str] = None        # 후원자 이메일 (Ko-fi 연동용)
    amount: float                            # 후원 금액
    currency: str = "USD"                    # 통화
    message: str = ""                        # 후원 메시지
    status: str = "verified"                 # "pending" | "verified" | "rejected"
    verified_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "donations"
        use_state_management = True
