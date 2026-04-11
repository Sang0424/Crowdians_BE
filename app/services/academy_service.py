# app/services/academy_service.py

from datetime import datetime, timezone
from bson import ObjectId

from app.models.user import User
from app.models.academy import KnowledgeCard, CardResponse
from app.services.user_service import check_daily_reset
import random

POOL_SIZE = 50



async def get_daily_cards(user: User | None, ticket_index: int, locale: str = "ko") -> list[dict]:
    """일일 지식카드 5장을 조회합니다. (ArchivePost 연동 카드 및 일반 퀴즈)"""
    # 0. 로케일 정규화 (en-US -> en 등)
    if locale and len(locale) > 2:
        locale = locale[:2].lower()
    
    print(f"[Academy] Fetching cards for User: {user.uid if user else 'guest'}, Locale: {locale}, Ticket: {ticket_index}")
    # 1. 일일 초기화 체크
    if user and check_daily_reset(user):
        await user.save()

    # 2. 이미 답변한 질문(아카이브 답변 기준) 및 본인이 작성한 질문 제외
    from app.models.archive import ArchiveAnswer, ArchivePost
    from beanie.operators import NotIn, Or, In

    if user:
        # 자신이 이미 답변한 포스트 ID 목록
        answered_posts = await ArchiveAnswer.find(ArchiveAnswer.author_id == user.uid).to_list()
        answered_post_ids = [ans.post_id for ans in answered_posts]

        # 자신이 작성한 포스트 ID 목록
        my_posts = await ArchivePost.find(ArchivePost.author_id == user.uid).to_list()
        my_post_ids = [str(p.id) for p in my_posts]
    else:
        answered_post_ids = []
        my_post_ids = []

    # 🌟 [추가] 유효하지 않은 질문(is_valid_question == False) 제외
    invalid_posts = await ArchivePost.find(ArchivePost.is_valid_question == False).to_list()
    invalid_post_ids = [str(p.id) for p in invalid_posts]

    excluded_linked_ids = list(set(answered_post_ids + my_post_ids + invalid_post_ids))
    print(f"[Academy] Excluded Linked IDs: {len(excluded_linked_ids)} (Reason: Answered, Own, or Invalid)")

    # 3. 직접 응답한 카드(CardResponse) ID 목록 조회
    if user:
        responded_records = await CardResponse.find(CardResponse.user_id == user.uid).to_list()
        responded_card_ids = [ObjectId(rec.card_id) for rec in responded_records]
    else:
        responded_card_ids = []
    
    # 4. 공용 제외 쿼리 생성 (언어 필터 추가)
    query_filters = [
        KnowledgeCard.is_migrated == False,
        KnowledgeCard.locale == locale,
        NotIn(KnowledgeCard.id, responded_card_ids)
    ]
    
    if excluded_linked_ids:
        query_filters.append(
            Or(
                KnowledgeCard.linked_post_id == None,
                KnowledgeCard.linked_post_id == "",
                NotIn(KnowledgeCard.linked_post_id, excluded_linked_ids)
            )
        )
    
    
    # ── 1단계: Vote 타입 우선 확보 (최대한 3장) ──
    # POOL_SIZE만큼 후보군을 가져와 그 안에서 무작위로 선택합니다.
    vote_candidates = await KnowledgeCard.find(
        *query_filters, KnowledgeCard.type == "vote"
    ).sort([("priority", -1), ("created_at", -1)]).limit(POOL_SIZE).to_list()
    
    vote_cards = random.sample(vote_candidates, min(3, len(vote_candidates)))
    print(f"[Academy] Obtained Vote Cards: {len(vote_cards)} (from {len(vote_candidates)} candidates)")
    
    # ── 2단계: 부족한 만큼 Teach 타입으로 채우기 (최대 5장 확보를 목표) ──
    needed_teach = 5 - len(vote_cards)
    if needed_teach > 0:
        teach_candidates = await KnowledgeCard.find(
            *query_filters, KnowledgeCard.type == "teach"
        ).sort([("priority", -1), ("created_at", -1)]).limit(POOL_SIZE).to_list()
        
        teach_cards = random.sample(teach_candidates, min(needed_teach, len(teach_candidates)))
        print(f"[Academy] Obtained Teach Cards: {len(teach_cards)} (from {len(teach_candidates)} candidates)")
    else:
        teach_cards = []
    
    total_cards = vote_cards + teach_cards
    
    # ── 3단계: 그래도 5장이 안 되면 나머지 타입(quiz 등)에서 추가 확보 ──
    if len(total_cards) < 5:
        existing_ids = [c.id for c in total_cards]
        needed_extra = 5 - len(total_cards)
        
        extra_candidates = await KnowledgeCard.find(
            *query_filters,
            NotIn(KnowledgeCard.id, existing_ids)
        ).sort([("priority", -1), ("created_at", -1)]).limit(POOL_SIZE).to_list()
        
        extra_cards = random.sample(extra_candidates, min(needed_extra, len(extra_candidates)))
        total_cards += extra_cards
        print(f"[Academy] Obtained Extra Cards: {len(extra_cards)}")
    
    print(f"[Academy] Total Final Cards: {len(total_cards)}")
    if not total_cards:
        # Check if cards exist in DB without the is_migrated filter
        total_in_db = await KnowledgeCard.find(KnowledgeCard.locale == locale).count()
        if total_in_db > 0:
            print(f"[Academy] Warning: {total_in_db} cards exist in DB for locale '{locale}', but 0 matched filters (is_migrated=False). Check is_migrated flags.")
        else:
            print(f"[Academy] Warning: 0 cards found in DB for locale '{locale}'.")
    # 다양한 노출을 위해 섞어줌
    random.shuffle(total_cards)

    card_list = []
    for c in total_cards:
        card_list.append({
            "id": str(c.id),
            "type": c.type,
            "question": c.question,
            "content": c.content,
            "summary": c.summary or "",
            "choices": c.choices,
            "linked_post_id": c.linked_post_id
        })

    return card_list



async def start_academy_session(user: User | None) -> dict:
    """학습 세션을 시작합니다. 지식 티켓 1장을 소모합니다."""
    if not user:
        # 게스트의 경우 티켓 차감 없이 가상의 성공 응답 반환 (최대 5장 세션 가정)
        return {
            "success": True,
            "learningTickets": 0
        }

    if check_daily_reset(user):
        await user.save()
        
    if user.stats.learning_tickets <= 0:
        raise ValueError("남은 학습 티켓이 없습니다. 내일 다시 시도해 주세요.")

    if user.stats.trust < 100:
        raise ValueError("신뢰도가 낮아 학습을 진행할 수 없습니다.")
        
    # 세션 시작 시 1장 차감
    user.stats.learning_tickets -= 1
    await user.save()
    
    return {
        "success": True,
        "learningTickets": user.stats.learning_tickets
    }

async def submit_card_answer(user: User | None, card_id: str, answer: str | int, background_tasks: any = None) -> dict:
    """지식 카드 응답을 제출하고 정답 여부를 판별하여 보상을 지급합니다."""
    # 1. 일일 초기화 및 티켓 검사
    if user and check_daily_reset(user):
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
    if user and getattr(card, "linked_post_id", None):
        from app.services.archive_service import submit_archive_answer
        try:
            await submit_archive_answer(
                user, 
                card.linked_post_id, 
                str(answer),
                background_tasks=background_tasks
            )
        except Exception as e:
            print(f"Failed to submit archive answer via academy: {e}")

    # 🌟 3. [추가] 허니팟(어텐션 체크) 적발 로직
    if card.honeypot_answer and str(answer) == str(card.honeypot_answer):
        # 패널티: 신뢰도 대폭 차감
        penalty_trust = 50
        if user:
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
            "rewardIntelligence": 0,
            "message": "부정확한 답변을 선택하셨습니다. 신뢰도가 하락합니다."
        }

    # 4. 채점 (정답이 지정되지 않은 'vote'나 'teach'는 참여만으로 성공 처리)
    is_correct = True
    
    if card.type == "quiz" and card.correct_answer:
        # 고정 정답이 있는 퀴즈인 경우에만 체크
        is_correct = (str(card.correct_answer) == str(answer))

    # 🌟 5. [추가] 신뢰도 기반 가중치(Weight) 계산
    voting_weight = max(1, (user.stats.trust // 500) if user else 2) # 게스트는 기본 1000점(가중치 2) 가정

    exp_gained = 0
    gold_gained = 0
    trust_gained = 0
    int_gained = 0
    
    # 6. 보상 계산
    # RLHF(vote, teach) 목적의 데이터 수집인 경우 무조건 보상, 
    # 정답이 있는 퀴즈일 경우 정답일 때만 보상
    if is_correct:
        exp_gained = 10      # 기본 EXP
        gold_gained = 5     # 기본 Gold
        trust_gained = 1     # 신뢰도 상승
        int_gained = 3 if card.type == "teach" else 1 # 지능 상승
        
        if user:
            user.stats.exp += exp_gained
            user.stats.gold += gold_gained
            user.stats.trust += trust_gained
            user.stats.intelligence += int_gained
            
            # 레벨업 판정
            user.stats.process_level_up(max_stamina=user.max_stamina)
                
            # 🌟 7. [수정] 카드의 trust_count 증가 (단순 +1이 아닌 가중치 반영)
            card.trust_count += voting_weight
            
            await user.save()
            
        # 게스트든 유저든 카드의 통계 데이터는 저장해야 함
        await card.save()
    
    # 8. 카드 응답 내역 저장 (유저일 때만)
    if user:
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
        "rewardIntelligence": int_gained if is_correct else 0,
        "message": message
    }

async def reject_card_answer(user: User | None, card_id: str) -> dict:
    """Vote 타입 카드 등에서 둘 다 별로('Reject')를 선택한 경우 처리합니다."""
    if user and check_daily_reset(user):
        await user.save()
        
    from bson import ObjectId
    try:
        card = await KnowledgeCard.get(ObjectId(card_id))
    except Exception:
        raise ValueError("유효하지 않은 카드 ID입니다.")
        
    if not card:
        raise ValueError("카드를 찾을 수 없습니다.")

    # reject 시 소량의 신뢰도 보상(참여 보상)을 줄지 여부 결정, 일단 없음.
    if user:
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



async def submit_ab_vote(user: User | None, card_id: str, chosen_answer: str, unchosen_answer: str) -> dict:
    """A/B 테스트 방식의 투표를 처리하고 선호도 통계를 업데이트합니다."""
    # 1. 일일 초기화
    if user and check_daily_reset(user):
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
        if user:
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
            "isCorrect": False,
            "rewardExp": 0,
            "rewardGold": 0,
            "rewardTrust": -penalty_trust,
            "rewardIntelligence": 0,
            "message": "부정확한 답변을 선택하셨습니다. 신뢰도가 하락합니다.",
        }

    # 4. 신뢰도 기반 가중치 계산 (1000점당 1점의 가중치 등 정책에 맞게 조정 가능)
    voting_weight = max(1, (user.stats.trust // 500) if user else 2)

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
    int_gained = 1
    
    if user:
        user.stats.exp += exp_gained
        user.stats.gold += gold_gained
        user.stats.trust += trust_gained
        user.stats.intelligence += int_gained
        user.stats.process_level_up(max_stamina=user.max_stamina)
        await user.save()

    # 게스트든 유저든 카드 투표 데이터 저장
    await card.save()

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
                    chat_context=[m.model_dump() for m in original_post.chat_context],
                    ranked_answers=results,
                    domain_category=str(original_post.domain_category),
                    tags=original_post.tags,
                    total_matches_played=card.total_matches
                )
                await golden_data.insert()
                card.is_migrated = True

    if user:
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
        "rewardIntelligence": int_gained,
        "message": f"투표가 반영되었습니다. (영향력: {voting_weight}점)"
    }


async def sync_guest_academy_data(user: User, items: list) -> dict:
    """게스트 세션에서 쌓인 학습 데이터를 가입 시점에 일괄 동기화합니다."""
    total_exp = 0
    total_gold = 0
    total_trust = 0
    total_int = 0
    
    synced_count = 0
    
    from app.models.academy import CardResponse
    
    for item in items:
        # 이미 답변한 카드인지 중복 체크 방지 (선택 사항)
        exists = await CardResponse.find_one(
            CardResponse.user_id == user.uid,
            CardResponse.card_id == item.card_id
        )
        if exists:
            continue
            
        # 1. 정식 응답 로그 생성
        response_log = CardResponse(
            user_id=user.uid,
            card_id=item.card_id,
            answer=item.answer or item.chosen_answer,
            is_correct=item.is_correct,
            reward_exp=item.reward_exp,
            reward_gold=item.reward_gold,
            reward_trust=item.reward_trust,
        )
        await response_log.insert()
        
        # 2. 관련 서비스 연동 (Archive 등)
        # 퀴즈 보상 합산
        total_exp += item.reward_exp
        total_gold += item.reward_gold
        total_trust += item.reward_trust
        total_int += item.reward_intelligence
        
        # 3. ArchivePost 연동 처리 (있는 경우)
        try:
            card = await KnowledgeCard.get(ObjectId(item.card_id))
            if card and card.linked_post_id:
                from app.services.archive_service import submit_archive_answer
                await submit_archive_answer(
                    user, 
                    card.linked_post_id, 
                    str(item.answer or item.chosen_answer),
                )
                
                # A/B 투표인 경우 통계도 업데이트
                if card.type == "vote" and item.chosen_answer:
                    voting_weight = max(1, user.stats.trust // 500)
                    if not card.choice_matches: card.choice_matches = {}
                    if not card.choice_wins: card.choice_wins = {}
                    
                    chosen = str(item.chosen_answer)
                    unchosen = str(item.unchosen_answer or "")
                    
                    for ans in [chosen, unchosen]:
                        card.choice_matches[ans] = card.choice_matches.get(ans, 0) + 1
                        
                    card.choice_wins[chosen] = card.choice_wins.get(chosen, 0) + voting_weight
                    card.total_matches += 1
                    card.trust_count += voting_weight
                    await card.save()
                elif card.type in ["teach", "quiz"]:
                    card.trust_count += max(1, user.stats.trust // 500)
                    await card.save()
                    
        except Exception as e:
            print(f"[Sync] Failed to process card {item.card_id} for user {user.uid}: {e}")
            
        synced_count += 1
        
    # 유저 스탯 일괄 업데이트
    user.stats.exp += total_exp
    user.stats.gold += total_gold
    user.stats.trust += total_trust
    user.stats.intelligence += total_int
    user.stats.process_level_up(max_stamina=user.max_stamina)
    await user.save()
    
    return {
        "success": True,
        "syncedCount": synced_count,
        "rewardExp": total_exp,
        "rewardGold": total_gold
    }
