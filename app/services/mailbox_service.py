# app/services/mailbox_service.py

from datetime import datetime, timezone
from beanie import PydanticObjectId

from app.models.user import User
from app.models.mailbox import Mail

async def get_user_mails(user_id: str, skip: int = 0, limit: int = 20) -> tuple[list[Mail], int]:
    """유저의 메일함을 최신순으로 조회합니다."""
    query = {"user_id": user_id}
    
    total_count = await Mail.find(query).count()
    mails = await Mail.find(query).sort("-created_at").skip(skip).limit(limit).to_list()
    
    return mails, total_count

async def read_mail(user: User, mail_id: str) -> dict:
    """메일을 읽음 처리하고, 보상이 있다면 유저 스탯에 반영합니다."""
    try:
        mail = await Mail.get(PydanticObjectId(mail_id))
    except Exception:
        raise ValueError("유효하지 않은 메일 ID입니다.")
        
    if not mail or mail.user_id != user.uid:
        raise ValueError("메일을 찾을 수 없거나 권한이 없습니다.")
        
    if mail.is_read:
        raise ValueError("이미 읽고 보상을 수령한 메일입니다.")
        
    # 만료 기한 확인
    if mail.expires_at and mail.expires_at < datetime.now(timezone.utc):
        raise ValueError("만료된 메일입니다.")
        
    # 보상 수령 로직
    reward = mail.reward
    received_rewards = {
        "exp": 0, "gold": 0, "trust": 0, "stamina": 0
    }
    
    if reward.exp > 0 or reward.gold > 0 or reward.trust > 0 or reward.stamina > 0:
        user.stats.exp += reward.exp
        user.stats.gold += reward.gold
        user.stats.trust += reward.trust
        user.stats.stamina += reward.stamina
        
        # 경험치 상승에 따른 일괄 레벨업 처리 루프 (선택사항)
        while user.stats.exp >= user.stats.max_exp:
            user.stats.exp -= user.stats.max_exp
            user.stats.level += 1
            
        await user.save()
        
        received_rewards["exp"] = reward.exp
        received_rewards["gold"] = reward.gold
        received_rewards["trust"] = reward.trust
        received_rewards["stamina"] = reward.stamina

    # 메일 상태 업데이트
    mail.is_read = True
    await mail.save()
    
    return {
        "success": True,
        "message": "메일을 성공적으로 열었습니다.",
        "receivedRewards": received_rewards
    }

async def send_system_mail(user_id: str, title: str, content: str, exp: int=0, gold: int=0, trust: int=0, stamina: int=0, mail_type: str="system", reference_id: str = None):
    """시스템 포트에 의해 유저에게 특별 우편을 발송하는 내부 유틸 API"""
    new_mail = Mail(
        user_id=user_id,
        type=mail_type,
        title=title,
        content=content,
        reward={
            "exp": exp,
            "gold": gold,
            "trust": trust,
            "stamina": stamina
        },
        reference_id=reference_id
    )
    await new_mail.insert()
