# app/services/subscription_service.py

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from fastapi import HTTPException, Request

from app.core.config import settings
from app.models.user import User
from app.models.subscription import SubscriptionEvent

class SubscriptionService:
    LEMONSQUEEZY_API_URL = "https://api.lemonsqueezy.com/v1"

    @staticmethod
    async def create_checkout_url(user: User) -> str:
        """Lemon Squeezy Checkout URL 생성"""
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_data": {
                        "custom": {
                            "uid": user.uid  # 유저 식별을 위해 파라미터 전달
                        },
                        "email": user.email or ""
                    },
                    "product_options": {
                        "redirect_url": f"{settings.FRONTEND_URL}/settings/subscription?success=true"
                    }
                },
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": str(settings.LEMONSQUEEZY_STORE_ID)
                        }
                    },
                    "variant": {
                        "data": {
                            "type": "variants",
                            "id": str(settings.LEMONSQUEEZY_VARIANT_ID)
                        }
                    }
                }
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SubscriptionService.LEMONSQUEEZY_API_URL}/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.LEMONSQUEEZY_API_KEY}",
                    "Accept": "application/vnd.api+json",
                    "Content-Type": "application/vnd.api+json"
                }
            )
            
            if response.status_code != 201:
                # Lemon Squeezy 에러 로그 기록
                try:
                    error_data = response.json()
                    # Lemon Squeezy API v1 errors are in an array: {"errors": [{"detail": "..."}]}
                    errors = error_data.get("errors", [])
                    if isinstance(errors, list) and len(errors) > 0:
                        error_detail = errors[0].get("detail", str(errors[0]))
                    else:
                        error_detail = str(error_data)
                except Exception:
                    error_detail = response.text
                
                print(f"Lemon Squeezy API Error (Status {response.status_code}): {error_detail}")
                
                # 국제화된 에러 응답 반환
                from app.core.exceptions import DomainError
                raise DomainError(
                    message=f"Lemon Squeezy error: {error_detail}",
                    status_code=response.status_code if 400 <= response.status_code < 500 else 500,
                    code="SUBSCRIPTION.CHECKOUT_FAILED"
                )
            
            data = response.json()
            return data["data"]["attributes"]["url"]

    @staticmethod
    async def verify_webhook(request: Request) -> bool:
        """Lemon Squeezy Webhook 서명 검증"""
        signature = request.headers.get("X-Signature")
        if not signature:
            return False
        
        body = await request.body()
        secret = settings.LEMONSQUEEZY_WEBHOOK_SECRET.encode("utf-8")
        
        digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    @staticmethod
    async def handle_webhook(payload: Dict[str, Any]):
        """Lemon Squeezy Webhook 이벤트 처리"""
        meta = payload.get("meta", {})
        event_name = meta.get("event_name")
        data = payload.get("data", {})
        attributes = data.get("attributes", {})
        
        # 유저 UID 확인 (Checkout 생성 시 넣었던 custom 데이터)
        uid = meta.get("custom_data", {}).get("uid")
        if not uid:
            # 기존 구독 업데이트인 경우 attributes에서 확인 시도 (구현에 따라 다를 수 있음)
            # 여기서는 새로고침 로직을 위해 uid가 반드시 필요함
            print(f"Webhook received without UID: {event_name}")
            return

        user = await User.find_one(User.uid == uid)
        if not user:
            print(f"User not found for Webhook: {uid}")
            return

        # 구독 정보 추출
        sub_id = data.get("id")
        customer_id = attributes.get("customer_id")
        status = attributes.get("status")  # pydantic/lemonsqueezy docs 참고: active, cancelled, expired 등
        
        # 만료일/갱신일 처리
        renews_at_str = attributes.get("renews_at")
        ends_at_str = attributes.get("ends_at")
        
        renews_at = SubscriptionService._parse_date(renews_at_str)
        ends_at = SubscriptionService._parse_date(ends_at_str)

        # 1. 구독 이벤트 기록
        event = SubscriptionEvent(
            event_name=event_name,
            lemonsqueezy_id=str(sub_id),
            customer_id=customer_id,
            subscription_id=int(sub_id),
            variant_id=int(attributes.get("variant_id")),
            status=status,
            renews_at=renews_at,
            ends_at=ends_at,
            uid=uid,
            raw_data=payload
        )
        await event.insert()

        # 2. 유저 상태 업데이트
        if event_name in ["subscription_created", "subscription_updated"]:
            if status in ["active", "on_trial"]:
                user.subscription_plan = "premium"
                # 만료일은 renews_at 또는 ends_at 중 있는 것으로 설정
                user.subscription_expires_at = renews_at or ends_at
            else:
                user.subscription_plan = "free"
                
        elif event_name in ["subscription_cancelled"]:
            # 해지 예약 상태. 만료일까지는 프리미엄 유지
            user.subscription_plan = "premium"
            user.subscription_expires_at = ends_at
            
        elif event_name in ["subscription_expired", "subscription_payment_failed"]:
            user.subscription_plan = "free"
            user.subscription_expires_at = None

        # 프리미엄 유저라면 스태미나 충전/무제한 처리
        if user.subscription_plan == "premium":
            user.stats.stamina = 999
        
        user.lemonsqueezy_customer_id = str(customer_id)
        user.lemonsqueezy_subscription_id = str(sub_id)
        
        await user.save()

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            # Lemon Squeezy dates are ISO 8601
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
