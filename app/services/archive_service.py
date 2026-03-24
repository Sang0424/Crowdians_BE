# app/services/archive_service.py

from datetime import datetime, timezone
from beanie import PydanticObjectId

from app.models.user import User
from app.models.archive import ArchivePost, ArchiveAnswer
from app.models.academy import KnowledgeCard


from app.db.repository.archive_repository import archive_repo, archive_answer_repo
from app.services.mailbox_service import send_system_mail

async def create_archive_post(user: User, title: str, content: str, is_sos: bool = False, category: str = "general", bounty: int = 0, locale: str = "ko", target_user_id: str = None) -> str:
    """새로운 지식 도서관 질문을 등록합니다."""
    # 바운티(Bounty) 차감
    if bounty > 0:
        if user.stats.gold < bounty:
            raise ValueError("골드가 부족합니다.")
        
        user.stats.gold -= bounty
        from app.db.repository.user_repository import user_repo
        await user_repo.update(db_obj=user, obj_in={"stats": user.stats})

    # 직접 의뢰(Direct Commission)인 경우 상태를 'commissioned'로 설정
    status = "commissioned" if target_user_id else "open"
    
    post = await archive_repo.create(obj_in={
        "title": title,
        "content": content,
        "is_sos": is_sos,
        "category": category,
        "bounty": bounty,
        "author_id": user.uid,
        "locale": locale,
        "character_type": user.character.type if user.character else "unknown",
        "target_user_id": target_user_id,
        "status": status,
    })
    
    # 직접 의뢰인 경우 대상 유저에게 알림 메일 발송
    if target_user_id:
        await send_system_mail(
            user_id=target_user_id,
            title="🎯 새로운 직접 의뢰가 도착했습니다!",
            content=f"'{user.nickname}' 크라우디언님이 당신에게 직접 지식 의뢰를 보냈습니다.\n\n제목: {title}",
            mail_type="commission_request",
            reference_id=str(post.id)
        )
    
    # 아카데미(Academy)에서 풀 수 있도록 KnowledgeCard 생성 (일반 질문만)
    if not target_user_id:
        card = KnowledgeCard(
            type="teach",
            question=f"[{category}] {title}\n\n{content}",
            choices=[],
            correct_answer="",
            bounty=bounty,
            linked_post_id=str(post.id)
        )
        await card.insert()
    
    return str(post.id)


async def get_archive_list(sort: str, skip: int = 0, limit: int = 10, locale: str = "ko") -> tuple[list[ArchivePost], int]:
    """질문 목록을 페이지네이션으로 조회합니다. (posts, total_count) 반환."""
    # sort param (latest | popular | bounty | needed)
    sort_query = []
    if sort == "popular":
        sort_query = [("answer_count", -1), ("createdAt", -1)]
    elif sort == "bounty":  
        sort_query = [("bounty", -1), ("createdAt", -1)]
    elif sort == "needed":
        sort_query = [("answer_count", 1), ("createdAt", -1)]
    else:
        sort_query = [("createdAt", -1)]

    query = archive_repo.model.find(archive_repo.model.locale == locale)
    total_count = await query.count()
    posts = await query.sort(sort_query).skip(skip).limit(limit).to_list()
    return posts, total_count


async def toggle_bookmark(user_uid: str, post_id: str) -> bool:
    """아카이브 포스트 북마크 토글"""
    from app.db.repository.user_repository import user_repo
    user = await user_repo.get_by_uid(user_uid)
    if not user:
        raise ValueError("유효하지 않은 유저 UID입니다.")

    if not hasattr(user, "bookmarked_posts") or user.bookmarked_posts is None:
        user.bookmarked_posts = []
    
    if post_id in user.bookmarked_posts:
        user.bookmarked_posts.remove(post_id)
        is_bookmarked = False
    else:
        user.bookmarked_posts.append(post_id)
        is_bookmarked = True
    
    await user.save()
    return is_bookmarked


async def get_archive_post_detail(post_id: str, user_uid: str) -> dict:
    """질문 상세 정보와 상위 답변들을 가져옵니다."""
    try:
        post = await archive_repo.get_by_id(post_id)
    except Exception as e:
        import traceback
        print(f"Error in detail fetching post: {e}") 
        traceback.print_exc()
        raise ValueError(f"유효하지 않은 Post ID입니다. 에러: {e}")
        
    if not post:
        raise ValueError("질문 글을 찾을 수 없습니다.")
        
    answers = await archive_answer_repo.model.find(
        archive_answer_repo.model.post_id == post_id
    ).sort([("trust_count", -1)]).to_list()
    
    from app.db.repository.user_repository import user_repo
    from beanie.operators import In
    author_ids = list(set([ans.author_id for ans in answers] + [post.author_id]))
    users = await user_repo.model.find(In(user_repo.model.uid, author_ids)).to_list()
    user_dict = {u.uid: u for u in users}
    
    # 프론트에 맞게 매핑
    answer_responses = []
    for ans in answers:
        u = user_dict.get(ans.author_id)
        author_resp = {
            "id": ans.author_id,
            "nickname": u.nickname if u else "크라우디언",
            "trustCount": u.stats.trust if u else 0,
            "level": u.stats.level if u else 1,
            "characterType": u.character.type if u and getattr(u, 'character', None) else "unknown",
        }
        answer_responses.append({
            "id": str(ans.id),
            "postId": ans.post_id,
            "author": author_resp,
            "content": ans.content,
            "trustCount": ans.trust_count,
            "isTrustedByMe": user_uid in ans.voted_user_ids,
            "createdAt": ans.createdAt,
        })
        
    post_u = user_dict.get(post.author_id)
    post_author_resp = {
        "id": post.author_id,
        "nickname": post_u.nickname if post_u else "크라우디언",
        "trustCount": post_u.stats.trust if post_u else 0,
        "level": post_u.stats.level if post_u else 1,
        "characterType": post_u.character.type if post_u and getattr(post_u, 'character', None) else "unknown",
    }

    from app.db.repository.user_repository import user_repo
    me = await user_repo.get_by_uid(user_uid)
    is_bookmarked = False
    if me and post_id in (me.bookmarked_posts or []):
        is_bookmarked = True

    return {
        "id": str(post.id),
        "title": post.title,
        "content": post.content,
        "isSos": post.is_sos,
        "category": post.category,
        "bounty": post.bounty,
        "author": post_author_resp,
        "answerCount": post.answer_count,
        "targetUserId": post.target_user_id,
        "status": post.status,
        "createdAt": post.createdAt,
        "characterType": post_author_resp["characterType"],
        "isBookmarked": is_bookmarked,
        "isDirectCommission": bool(post.target_user_id),
        "answers": answer_responses,
    }


async def submit_archive_answer(user: User, post_id: str, content: str) -> str:
    """질문에 답변을 작성합니다."""
    try:
        post = await archive_repo.get_by_id(post_id)
    except Exception as e:
        import traceback
        print(f"Error in submit answer: {e}")
        traceback.print_exc()
        raise ValueError(f"유효하지 않은 Post ID입니다. 에러: {e}")
        
    if not post:
        raise ValueError("질문 글을 찾을 수 없습니다.")
        
    # 직접 의뢰인 경우, 권한 확인 (status가 'commissioned'이면 target_user_id만 가능)
    # 하지만 일반 답변도 허용할지 여부 결정 필요. 요구사항: 대상이 지정된 의뢰 글에 답변을 달 경우 상태 변경 및 보상.
    is_commissioned_expert = (post.target_user_id == user.uid)
    
    answer = await archive_answer_repo.create(obj_in={
        "post_id": post_id,
        "author_id": user.uid,
        "content": content,
    })
    
    # 캐싱용 answer_count 증가
    post.answer_count += 1
    post.updatedAt = datetime.now(timezone.utc)
    
    # 직접 의뢰 지정 전문가가 답변한 경우 상태 업데이트 및 보상
    if is_commissioned_expert and post.status == "commissioned":
        post.status = "answered"
        # 추가 보상 (Bonus Gold/Exp): 예를 들어 바운티의 50%를 보너스로 지급
        bonus_gold = int(post.bounty * 0.5)
        bonus_exp = 100 # 고정 보너스 경험치
        
        user.stats.gold += bonus_gold
        user.stats.exp += bonus_exp
        
        # 레벨업 체크
        while user.stats.exp >= user.stats.max_exp:
            user.stats.exp -= user.stats.max_exp
            user.stats.level += 1
            
        await user.save()
        
        # 의뢰자에게 답변 알림 발송
        await send_system_mail(
            user_id=post.author_id,
            title="✅ 의뢰한 답변이 등록되었습니다!",
            content=f"'{user.nickname}' 전문가님이 당신의 지식 의뢰에 답변을 남겼습니다.",
            mail_type="commission_answered",
            reference_id=str(post.id)
        )

    await archive_repo.update(db_obj=post, obj_in={
        "answer_count": post.answer_count, 
        "updatedAt": post.updatedAt,
        "status": post.status
    })
    
    return str(answer.id)


async def reject_commission(user: User, post_id: str) -> bool:
    """직접 의뢰를 거절합니다."""
    try:
        post = await archive_repo.get_by_id(post_id)
    except Exception:
        raise ValueError("유효하지 않은 Post ID입니다.")
        
    if not post:
        raise ValueError("질문 글을 찾을 수 없습니다.")
        
    if post.target_user_id != user.uid:
        raise ValueError("의뢰를 거절할 권한이 없습니다.")
        
    if post.status != "commissioned":
        raise ValueError("거절할 수 있는 상태가 아닙니다.")
        
    post.status = "rejected"
    await archive_repo.update(db_obj=post, obj_in={"status": post.status})
    
    # 의뢰자(A)에게 바운티 환불
    if post.bounty > 0:
        from app.db.repository.user_repository import user_repo
        author = await user_repo.get_by_uid(post.author_id)
        if author:
            author.stats.gold += post.bounty
            await user_repo.update(db_obj=author, obj_in={"stats": author.stats})

    # 의뢰자(A)에게 거절 알림 발송
    await send_system_mail(
        user_id=post.author_id,
        title="❌ 의뢰가 거절되었습니다.",
        content=f"'{user.nickname}' 크라우디언님이 당신의 직접 의뢰를 정중히 거절하였습니다.",
        mail_type="commission_reject",
        reference_id=str(post.id)
    )
    
    return True


async def toggle_trust_vote(user: User, answer_id: str) -> dict:
    """답변에 신뢰함(투표)을 토글합니다."""
    try:
        answer = await archive_answer_repo.get(PydanticObjectId(answer_id))
    except Exception:
        raise ValueError("유효하지 않은 Answer ID입니다.")
        
    if not answer:
        raise ValueError("답변을 찾을 수 없습니다.")
        
    # 자기 자신 답변에 추천 불가 정책
    if answer.author_id == user.uid:
        raise ValueError("자신의 답변에는 투표할 수 없습니다.")
        
    if user.uid in answer.voted_user_ids:
        # 이미 투표했으면 취소
        answer.voted_user_ids.remove(user.uid)
        answer.trust_count -= 1
        is_trusted = False
    else:
        # 투표
        answer.voted_user_ids.append(user.uid)
        answer.trust_count += 1
        is_trusted = True
        
    await archive_answer_repo.update(db_obj=answer, obj_in={"voted_user_ids": answer.voted_user_ids, "trust_count": answer.trust_count})
    
    # 추천/취소 시 작성자 Trust 스탯 증감
    from app.db.repository.user_repository import user_repo
    author = await user_repo.get_by_uid(answer.author_id)
    if author:
        # 매 추천마다 +5, 취소 시 -5
        if is_trusted:
            author.stats.trust += 5
        else:
            author.stats.trust -= 5
        await user_repo.update(db_obj=author, obj_in={"stats": author.stats})

    # 신뢰도 보상 및 특별 로직 (trust_count == 10 달성 최초 1회 등)
    if is_trusted and answer.trust_count == 10:
        # KnowledgeCard로 자동 승격
        await _promote_to_knowledge_card(answer)

    return {
        "isTrusted": is_trusted,
        "trustCount": answer.trust_count,
    }


async def _promote_to_knowledge_card(answer: ArchiveAnswer):
    """신뢰도 10 달성 시 Golden Dataset용 지식카드로 만드는 내부 로직."""
    try:
        post = await archive_repo.get_by_id(answer.post_id)
    except Exception:
        return
        
    if not post:
        return
        
    card = KnowledgeCard(
        type="teach",     # 주관식 또는 정답 있는 케이스
        question=post.title,
        correct_answer=answer.content,
        bounty=10,
        trust_count=answer.trust_count,
        source_message_id=str(answer.id)
    )
    await card.insert()


async def get_user_asked_posts(uid: str, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    """유저가 작성한 질문 목록 조회 (ArchiveActivityItem 형식)"""
    query = ArchivePost.find(ArchivePost.author_id == uid)
    total = await query.count()
    posts = await query.sort(-ArchivePost.createdAt).skip(skip).limit(limit).to_list()
    
    items = []
    for p in posts:
        items.append({
            "id": str(p.id),
            "type": "quest" if (p.is_sos or p.bounty > 0) else "post",
            "title": p.title,
            "status": p.status,
            "category": p.category,
            "isSOS": p.is_sos,
            "createdAt": p.createdAt
        })
    return items, total


async def get_user_answered_posts(uid: str, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    """유저가 작성한 답변 목록 조회 (ArchiveActivityItem 형식)"""
    query = ArchiveAnswer.find(ArchiveAnswer.author_id == uid)
    total = await query.count()
    answers = await query.sort(-ArchiveAnswer.createdAt).skip(skip).limit(limit).to_list()
    
    items = []
    for a in answers:
        post = await ArchivePost.get(a.post_id)
        items.append({
            "id": str(post.id) if post else str(a.id),
            "type": "comment",
            "title": post.title if post else "삭제된 질문",
            "status": post.status if post else "unknown",
            "category": post.category if post else "unknown",
            "isSOS": post.is_sos if post else False,
            "createdAt": a.createdAt
        })
    return items, total


async def get_user_bookmarked_posts(user: User, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    """유저가 북마크한 질문 목록 조회 (ArchiveActivityItem 형식)"""
    bookmarked_ids = user.bookmarked_posts or []
    if not bookmarked_ids:
        return [], 0
        
    from beanie import PydanticObjectId
    obj_ids = []
    for pid in bookmarked_ids:
        try:
            obj_ids.append(PydanticObjectId(pid))
        except:
            continue
            
    if not obj_ids:
        return [], 0

    from beanie.operators import In
    query = ArchivePost.find(In(ArchivePost.id, obj_ids))
    total = await query.count()
    posts = await query.sort(-ArchivePost.createdAt).skip(skip).limit(limit).to_list()
    
    items = []
    for p in posts:
        items.append({
            "id": str(p.id),
            "type": "post",
            "title": p.title,
            "status": p.status,
            "category": p.category,
            "isSOS": p.is_sos,
            "createdAt": p.createdAt
        })
    return items, total

async def get_user_voted_answers(uid: str, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
    """유저가 신뢰함 투표한 답변 목록 조회 (ArchiveActivityItem 형식)"""
    query = ArchiveAnswer.find({"voted_user_ids": uid})
    total = await query.count()
    answers = await query.sort(-ArchiveAnswer.createdAt).skip(skip).limit(limit).to_list()
    
    items = []
    for a in answers:
        post = await ArchivePost.get(a.post_id)
        items.append({
            "id": str(post.id) if post else str(a.id),
            "type": "comment",
            "title": post.title if post else "삭제된 질문",
            "status": post.status if post else "unknown",
            "category": post.category if post else "unknown",
            "isSOS": post.is_sos if post else False,
            "createdAt": a.createdAt
        })
    return items, total
