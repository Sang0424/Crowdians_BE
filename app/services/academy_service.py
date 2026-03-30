# app/services/academy_service.py

from datetime import datetime, timezone

from app.models.user import User
from app.models.academy import KnowledgeCard, CardResponse
from app.services.user_service import check_daily_reset



async def get_daily_cards(user: User, ticket_index: int) -> list[dict]:
    """일일 지식카드 5장을 조회합니다. (임시로 랜덤 5장)"""
    # 1. 일일 초기화 체크
    if check_daily_reset(user):
        await user.save()
        
    # 2. 사실상 프론트엔드에서 ticketIndex로 페이지네이션/요청을 구분합니다.
    
    # DB에 카드가 없는 경우 임시 데이터
    count = await KnowledgeCard.count()
    if count == 0:
        sample_cards = [
            KnowledgeCard(type="vote", question="다음 중 파이썬의 프레임워크는?", choices=["Spring", "FastAPI"], correct_answer=1, bounty=10),
            KnowledgeCard(type="vote", question="Pico는 어떤 성격일까?", choices=["시니컬하다", "다정하고 호기심많다"], correct_answer=1, bounty=15),
            KnowledgeCard(type="question", question="오늘의 날씨는?", correct_answer="맑음", bounty=20),
            KnowledgeCard(type="quiz", question="2 + 2 = ?", correct_answer=4, bounty=25),
        ]
        await KnowledgeCard.insert_many(sample_cards)
        
    # 이미 푼 문제는 거르지 않고, 랜덤으로 5개 반환 리스트(간단히 앞 5개)
    cards = await KnowledgeCard.find().limit(5).to_list()
    
    return [
        {
            "id": str(c.id),
            "type": c.type,
            "question": c.question,
            "content": c.content,
            "choices": c.choices,
            "bounty": c.bounty,
        }
        for c in cards
    ]

async def start_academy_session(user: User) -> dict:
    if check_daily_reset(user):
        await user.save()
        
    if user.stats.learning_tickets <= 0:
        raise ValueError("남은 학습 티켓이 없습니다. 광고 충전이 필요합니다.")

    if user.stats.trust < 100:
        raise ValueError("신뢰도가 낮아 학습을 진행할 수 없습니다.")
        
    # 세션 시작 시 1장 차감
    user.stats.learning_tickets -= 1
    await user.save()
    
    return {
        "success": True,
        "learningTickets": user.stats.learning_tickets
    }

async def submit_card_answer(user: User, card_id: str, answer: str | int) -> dict:
    """지식 카드 응답을 제출하고 정답 여부를 판별하여 보상을 지급합니다."""
    # 1. 일일 초기화 및 티켓 검사
    if check_daily_reset(user):
        await user.save()
        
    # 2. 카드 조회
    from bson import ObjectId
    try:
        card = await KnowledgeCard.get(ObjectId(card_id))
    except Exception:
        raise ValueError("유효하지 않은 카드 ID입니다.")
        
    if not card:
        raise ValueError("카드를 찾을 수 없습니다.")
        
    # 만약 아카데미 카드가 Archive 연동 카드라면, 아카이브 답변으로도 등록합니다 (동기화)
    if getattr(card, "linked_post_id", None):
        from app.services.archive_service import submit_archive_answer
        try:
            await submit_archive_answer(user, card.linked_post_id, str(answer))
        except Exception as e:
            print(f"Failed to submit archive answer via academy: {e}")

    # 3. 채점
    is_correct = True

    exp_gained = 0
    gold_gained = 0
    trust_gained = 0
    
    if is_correct:
        exp_gained = 5      # 퀴즈 정답 EXP
        gold_gained = card.bounty
        trust_gained = 1    # 신뢰도 상승
        
        user.stats.exp += exp_gained
        user.stats.gold += gold_gained
        user.stats.trust += trust_gained
        
        # 레벨업 판정
        if user.stats.exp >= user.stats.max_exp:
            user.stats.exp -= user.stats.max_exp
            user.stats.level += 1
            user.stats.stamina = user.stats.max_stamina
            
        # 카드의 trust_count 증가 (골든 데이터셋 지표)
        card.trust_count += 1
        await card.save()
        
    await user.save()
    
    # 5. 카드 응답 내역 저장
    response_log = CardResponse(
        user_id=user.uid,
        card_id=card_id,
        answer=answer,
        is_correct=is_correct,
        reward_exp=exp_gained,
        reward_gold=gold_gained,
        reward_trust=trust_gained,
    )
    await response_log.insert()
    
    return {
        "isCorrect": is_correct,
        "rewardExp": exp_gained,
        "rewardGold": gold_gained,
        "rewardTrust": trust_gained,
        "message": "소중한 의견이 기록되었습니다! 보상을 획득하셨습니다."
    }

async def reject_card_answer(user: User, card_id: str) -> dict:
    """Vote 타입 카드 등에서 둘 다 별로('Reject')를 선택한 경우 처리합니다."""
    # 티켓은 차감할지 말지에 대한 기획 정책: 일반적으로 차감.
    if check_daily_reset(user):
        await user.save()
        
    from bson import ObjectId
    try:
        card = await KnowledgeCard.get(ObjectId(card_id))
    except Exception:
        raise ValueError("유효하지 않은 카드 ID입니다.")
        
    if not card:
        raise ValueError("카드를 찾을 수 없습니다.")

    # reject 시 소량의 신뢰도 보상(참여 보상)을 줄지 여부 결정, 일단 없음.
    await user.save()
    
    response_log = CardResponse(
        user_id=user.uid,
        card_id=card_id,
        answer="REJECTED",
        is_correct=False,
        is_rejected=True,
    )
    await response_log.insert()
    
    return {
        "success": True,
        "message": "답변을 모두 거절(Reject)했습니다. 데이터셋 개선에 반영됩니다."
    }

async def recharge_ticket(user: User) -> dict:
    """하루 최대 5번 광고 시청 후 티켓을 1장 충전합니다."""
    if check_daily_reset(user):
        await user.save()
        
    if user.stats.ticket_recharges_today >= 5:
        raise ValueError("하루 최대 티켓 충전 횟수(5회)를 초과했습니다.")
        
    user.stats.learning_tickets += 1
    user.stats.ticket_recharges_today += 1
    await user.save()
    
    return {
        "success": True,
        "ticketsRemaining": user.stats.learning_tickets,
        "rechargesToday": user.stats.ticket_recharges_today,
        "message": "티켓이 1장 충전되었습니다."
    }
