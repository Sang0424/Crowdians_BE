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

    # 3. 공통 제외 쿼리 생성
    base_filter = KnowledgeCard.find(
        KnowledgeCard.is_migrated == False,
        Or(
            KnowledgeCard.linked_post_id == None,
            NotIn(KnowledgeCard.linked_post_id, excluded_linked_ids)
        ) if excluded_linked_ids else {}
    )

    import random
    
    # ── Teach 타입 2장 확보 ──
    teach_cards = await base_filter.find(
        KnowledgeCard.type == "teach"
    ).sort([("priority", -1), ("created_at", -1)]).limit(2).to_list()
    
    # ── Vote 타입 3장 확보 ──
    vote_cards = await base_filter.find(
        KnowledgeCard.type == "vote"
    ).sort([("priority", -1), ("created_at", -1)]).limit(3).to_list()
    
    # 부족한 카드 보충 (총 5장이 되도록)
    total_cards = teach_cards + vote_cards
    if len(total_cards) < 5:
        existing_ids = [c.id for c in total_cards]
        needed = 5 - len(total_cards)
        extra_cards = await base_filter.find(
            NotIn(KnowledgeCard.id, existing_ids)
        ).sort([("priority", -1), ("created_at", -1)]).limit(needed).to_list()
        total_cards += extra_cards
    
    # 다양한 노출을 위해 섞어줌
    random.shuffle(total_cards)

    return [
        {
            "id": str(c.id),
            "type": c.type,
            "question": c.question,
            "content": c.content,
            "summary": c.summary or "",
            "choices": c.choices,
            "linked_post_id": c.linked_post_id,
        }
        for c in total_cards
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

    # 🌟 3. [추가] 허니팟(어텐션 체크) 적발 로직
    if card.honeypot_answer and str(answer) == str(card.honeypot_answer):
        # 패널티: 신뢰도 대폭 차감
        penalty_trust = 50
        user.stats.trust = max(0, user.stats.trust - penalty_trust)
        await user.save()
        
        # 패널티 로그 기록
        response_log = CardResponse(
            user_id=user.uid,
            card_id=card_id,
            answer=answer,
            is_correct=False,
            is_rejected=False,
            reward_trust=-penalty_trust # 음수 기록
        )
        await response_log.insert()
        
        return {
            "isCorrect": False,
            "rewardExp": 0,
            "rewardGold": 0,
            "rewardTrust": -penalty_trust,
            "message": "부정확한 답변을 선택하셨습니다. 신뢰도가 하락합니다."
        }

    # 4. 채점 (정답이 지정되지 않은 'vote'나 'teach'는 참여만으로 성공 처리)
    is_correct = True
    
    if card.type == "quiz" and card.correct_answer:
        # 고정 정답이 있는 퀴즈인 경우에만 체크
        is_correct = (str(card.correct_answer) == str(answer))

    # 🌟 5. [추가] 신뢰도 기반 가중치(Weight) 계산
    voting_weight = max(1, user.stats.trust // 500)

    exp_gained = 0
    gold_gained = 0
    trust_gained = 0
    
    # 6. 보상 계산
    # RLHF(vote, teach) 목적의 데이터 수집인 경우 무조건 보상, 
    # 정답이 있는 퀴즈일 경우 정답일 때만 보상
    if is_correct:
        exp_gained = 10      # 기본 EXP
        gold_gained = 5     # 기본 Gold
        trust_gained = 1     # 신뢰도 상승
        
        user.stats.exp += exp_gained
        user.stats.gold += gold_gained
        user.stats.trust += trust_gained
        
        # 레벨업 판정
        user.stats.process_level_up()
            
        # 🌟 7. [수정] 카드의 trust_count 증가 (단순 +1이 아닌 가중치 반영)
        card.trust_count += voting_weight
        await card.save()
        
    await user.save()
    
    # 8. 카드 응답 내역 저장
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
    
    # 메시지 커스터마이징
    item_type_str = "참여" if card.type in ["vote", "teach"] else "정답"
    message = f"지식 {item_type_str} 보상을 획득하셨습니다! (영향력: {voting_weight}점)"
    if card.type == "quiz":
        message = f"정답입니다! 지식이 한 층 깊어졌습니다. (영향력: {voting_weight}점)" if is_correct else "아쉽게도 오답입니다. 다음 기회를 노려보세요!"

    return {
        "isCorrect": is_correct,
        "rewardExp": exp_gained,
        "rewardGold": gold_gained,
        "rewardTrust": trust_gained,
        "message": message
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



async def submit_ab_vote(user: User, card_id: str, chosen_answer: str, unchosen_answer: str) -> dict:
    """A/B 테스트 방식의 투표를 처리하고 선호도 통계를 업데이트합니다."""
    # 1. 일일 초기화
    if check_daily_reset(user):
        await user.save()

    # 2. 카드 조회
    from bson import ObjectId
    try:
        card = await KnowledgeCard.get(ObjectId(card_id))
    except Exception:
        raise ValueError("유효하지 않은 카드 ID입니다.")
        
    if not card or card.is_migrated:
        raise ValueError("카드를 찾을 수 없거나 이미 마이그레이션이 완료되었습니다.")

    # 🌟 3. 허니팟(어텐션 체크) 검사
    # A/B 테스트에서 chosen_answer가 허니팟이면 패널티
    if card.honeypot_answer and str(chosen_answer) == str(card.honeypot_answer):
        penalty_trust = 50
        user.stats.trust = max(0, user.stats.trust - penalty_trust)
        await user.save()
        
        response_log = CardResponse(
            user_id=user.uid,
            card_id=card_id,
            answer=chosen_answer,
            is_correct=False,
            reward_trust=-penalty_trust
        )
        await response_log.insert()
        
        return {
            "success": False,
            "message": "부정확한 답변을 선택하셨습니다. 신뢰도가 하락합니다.",
            "rewardTrust": -penalty_trust
        }

    # 4. 신뢰도 기반 가중치 계산 (1000점당 1점의 가중치 등 정책에 맞게 조정 가능)
    voting_weight = max(1, user.stats.trust // 500)

    # 5. 통계 업데이트
    if not card.choice_matches: card.choice_matches = {}
    if not card.choice_wins: card.choice_wins = {}

    for ans in [chosen_answer, unchosen_answer]:
        card.choice_matches[ans] = card.choice_matches.get(ans, 0) + 1
        if ans not in card.choice_wins: card.choice_wins[ans] = 0
            
    card.choice_wins[chosen_answer] += voting_weight
    card.total_matches += 1

    # 6. 보상 지급 (기존 보상 로직 통합)
    exp_gained = 10
    gold_gained = 5
    trust_gained = 1
    
    user.stats.exp += exp_gained
    user.stats.gold += gold_gained
    user.stats.trust += trust_gained
    user.stats.process_level_up()
    await user.save()

    # 🌟 7. 골든 데이터셋 임계점 돌파 검사 (threshold = 100)
    MATCHES_THRESHOLD = 100
    if not card.is_migrated and card.total_matches >= MATCHES_THRESHOLD:
        from app.models.golden_dataset import GoldenDataset
        from app.models.archive import ArchivePost
        
        # 승률 계산 및 정렬 (허니팟 제외)
        results = []
        for ans in card.choices:
            if card.honeypot_answer and str(ans) == str(card.honeypot_answer):
                continue # 허니팟 답변 제외
                
            wins = card.choice_wins.get(ans, 0)
            matches = card.choice_matches.get(ans, 0)
            win_rate = (wins / matches) if matches > 0 else 0
            
            results.append({
                "answer": ans,
                "wins": wins,
                "matches": matches,
                "win_rate": win_rate
            })
            
        results.sort(key=lambda x: x["win_rate"], reverse=True)
        for i, res in enumerate(results):
            res["rank"] = i + 1
            
        # ArchivePost 연동 데이터 조회
        if card.linked_post_id:
            original_post = await ArchivePost.get(ObjectId(card.linked_post_id))
            if original_post:
                golden_data = GoldenDataset(
                    raw_prompt=original_post.raw_prompt,
                    original_ai_answer=original_post.original_ai_answer,
                    ranked_answers=results,
                    domain_category=str(original_post.domain_category),
                    tags=original_post.tags,
                    total_matches_played=card.total_matches
                )
                await golden_data.insert()
                card.is_migrated = True

    await card.save()

    # 응답 로그 기록
    response_log = CardResponse(
        user_id=user.uid,
        card_id=card_id,
        answer=chosen_answer,
        is_correct=True,
        reward_exp=exp_gained,
        reward_gold=gold_gained,
        reward_trust=trust_gained,
    )
    await response_log.insert()

    return {
        "success": True,
        "isCorrect": True,
        "rewardExp": exp_gained,
        "rewardGold": gold_gained,
        "rewardTrust": trust_gained,
        "message": f"투표가 반영되었습니다. (영향력: {voting_weight}점)"
    }
