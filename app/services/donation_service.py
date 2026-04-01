# app/services/donation_service.py

from datetime import datetime, timezone
from typing import List, Optional

from app.core.config import settings
from app.models.donation import Donation
from app.models.user import User
from app.schemas.donation import KofiWebhookData


class DonationService:
    """후원 및 칭호 관리 서비스"""

    @staticmethod
    async def process_kofi_webhook(data: KofiWebhookData) -> bool:
        """Ko-fi 웹훅 데이터를 처리하여 후원 기록을 생성하고 유저 칭호를 업데이트합니다."""
        
        # 1. Verification Token 검증
        if settings.KOFI_VERIFICATION_TOKEN and data.verification_token != settings.KOFI_VERIFICATION_TOKEN:
            return False

        # 2. 중복 체크 (transaction_id 기준)
        existing = await Donation.find_one(Donation.platform_tx_id == data.kofi_transaction_id)
        if existing:
            return True # 이미 처리됨 (Idempotency)

        # 3. Donation 기록 생성
        donation = Donation(
            platform="kofi",
            platform_tx_id=data.kofi_transaction_id,
            donor_name=data.from_name,
            donor_email=data.email,
            amount=float(data.amount),
            currency=data.currency,
            message=data.message or "",
            verified_at=datetime.now(timezone.utc),
            created_at=data.timestamp or datetime.now(timezone.utc)
        )

        # 4. 유저 매칭 (이메일 기준)
        user = await User.find_one(User.email == data.email)
        if user:
            donation.user_uid = user.uid
            await donation.insert()
            
            # 5. 유저 칭호 및 티어 업데이트
            await DonationService.update_user_donation_tier(user, donation.amount)
        else:
            # 매칭되는 유저가 없더라도 기록은 보존
            await donation.insert()

        return True

    @staticmethod
    async def update_user_donation_tier(user: User, new_amount: float):
        """유저의 누적 후원 금액을 업데이트하고 칭호 등급을 계산하여 해금합니다."""
        user.total_donated += new_amount
        
        # 칭호 등급 기준 (USD)
        # Pioneer: $1+, Explorer: $10+, Guardian: $50+
        
        new_titles = []
        new_tier = user.donation_tier
        
        if user.total_donated >= 50.0:
            new_tier = "guardian"
            new_titles = ["pioneer", "explorer", "guardian"]
        elif user.total_donated >= 10.0:
            if new_tier != "guardian":
                new_tier = "explorer"
            new_titles = ["pioneer", "explorer"]
        elif user.total_donated >= 1.0:
            if new_tier not in ["explorer", "guardian"]:
                new_tier = "pioneer"
            new_titles = ["pioneer"]

        # 중복 제거 및 업데이트
        updated_titles = list(set(user.available_titles + new_titles))
        
        # 만약 티어가 올라갔다면 자동으로 해당 티어의 칭호를 현재 칭호로 설정 (선택 사항)
        # 여기서는 가장 높은 등급의 칭호를 자동으로 장착하도록 함
        if new_tier != "none" and new_tier != user.donation_tier:
            user.donation_tier = new_tier
            # stats.title 에도 반영 (i18n 처리는 프론트엔드에서 키값으로 수행)
            # 칭호 키값: "pioneer" | "explorer" | "guardian"
            user.stats.title = new_tier 

        user.available_titles = updated_titles
        await user.save()

    @staticmethod
    async def get_my_donations(user_uid: str) -> List[Donation]:
        """특정 유저의 후원 내역을 조회합니다."""
        return await Donation.find(Donation.user_uid == user_uid).sort("-created_at").to_list()

    @staticmethod
    async def update_user_title(user: User, title_key: str) -> bool:
        """유저가 보유한 칭호 중 하나로 현재 칭호를 변경합니다."""
        if title_key == "" or title_key in user.available_titles:
            user.stats.title = title_key
            await user.save()
            return True
        return False
