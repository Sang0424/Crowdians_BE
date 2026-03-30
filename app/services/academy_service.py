# app/services/academy_service.py

from datetime import datetime, timezone

from app.models.user import User
from app.models.academy import KnowledgeCard, CardResponse
from app.services.user_service import check_daily_reset



async def get_daily_cards(user: User, ticket_index: int) -> list[dict]:
    """일일 지식카드 5장을 조회합니다. (ArchivePost 연동 카드 및 일반 퀴즈)"""
    # 1. 일일 초기화 체크
    if check_daily_reset(user):
        await user.save()

    # 2. 이미 답변한 질문(아카이브 답변 기준) 및 본인이 작성한 질문 제외
    from app.models.archive import ArchiveAnswer, ArchivePost
    from beanie.operators import NotIn, Or, In

    # 자신이 이미 답변한 포스트 ID 목록
    answered_posts = await ArchiveAnswer.find(ArchiveAnswer.author_id == user.uid).to_list()
    answered_post_ids = [ans.post_id for ans in answered_posts]

    # 자신이 작성한 포스트 ID 목록
    my_posts = await ArchivePost.find(ArchivePost.author_id == user.uid).to_list()
    my_post_ids = [str(p.id) for p in my_posts]

    excluded_linked_ids = list(set(answered_post_ids + my_post_ids))

    # 3. 카드 조회 
    # linked_post_id 가 없거나 (일반 퀴즈), 
    # linked_post_id 가 있더라도 excluded_linked_ids 에 없는 것만 가져옴
    if excluded_linked_ids:
        query = KnowledgeCard.find(
            Or(
                KnowledgeCard.linked_post_id == None,
                NotIn(KnowledgeCard.linked_post_id, excluded_linked_ids)
            )
        )
    else:
        query = KnowledgeCard.find()

    # SOS 게시글 기반 카드 우선순위 (priority가 높은 순, 그 다음 최신순)
    cards = await query.sort([("priority", -1), ("created_at", -1)]).limit(5).to_list()

    # 4. 연동된 ArchivePost에서 summary 가져오기
    linked_post_ids = [c.linked_post_id for c in cards if c.linked_post_id]
    posts_map = {}
    if linked_post_ids:
        posts = await ArchivePost.find(In(ArchivePost.id, linked_post_ids)).to_list()
        posts_map = {str(p.id): p for p in posts}

    return [
        {
            "id": str(c.id),
            "type": c.type,
            "question": c.question,
            "content": c.content,
            "summary": posts_map.get(c.linked_post_id).summary if c.linked_post_id and c.linked_post_id in posts_map else "",
            "choices": c.choices,
            "linked_post_id": c.linked_post_id,
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
        exp_gained = 10      # 퀴즈 정답 EXP (고정)
        gold_gained = 5     # 퀴즈 정답 Gold (고정)
        trust_gained = 1     # 신뢰도 상승 (고정)
        
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


