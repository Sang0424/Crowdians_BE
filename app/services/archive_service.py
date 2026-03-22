# app/services/archive_service.py

from datetime import datetime, timezone
from bson import ObjectId

from app.models.user import User
from app.models.archive import ArchivePost, ArchiveAnswer
from app.models.academy import KnowledgeCard


from app.db.repository.archive_repository import archive_repo, archive_answer_repo

async def create_archive_post(user: User, title: str, content: str, is_sos: bool = False, category: str = "general", bounty: int = 0, locale: str = "ko") -> str:
    """새로운 지식 도서관 질문을 등록합니다."""
    post = await archive_repo.create(obj_in={
        "title": title,
        "content": content,
        "is_sos": is_sos,
        "category": category,
        "bounty": bounty,
        "author_id": user.uid,
        "locale": locale,
    })
    
    # 아카데미(Academy)에서 풀 수 있도록 KnowledgeCard 생성
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
        sort_query = [("answer_count", -1), ("created_at", -1)]
    elif sort == "bounty":  
        sort_query = [("bounty", -1), ("created_at", -1)]
    elif sort == "needed":
        sort_query = [("answer_count", 1), ("created_at", -1)]
    else:
        sort_query = [("created_at", -1)]

    query = archive_repo.model.find(archive_repo.model.locale == locale)
    total_count = await query.count()
    posts = await query.sort(sort_query).skip(skip).limit(limit).to_list()
    return posts, total_count


async def get_archive_post_detail(post_id: str, user_uid: str) -> dict:
    """질문 상세 정보와 상위 답변들을 가져옵니다."""
    try:
        post = await ArchivePost.get(ObjectId(post_id))
    except Exception:
        raise ValueError("유효하지 않은 Post ID입니다.")
        
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
        }
        answer_responses.append({
            "id": str(ans.id),
            "postId": ans.post_id,
            "author": author_resp,
            "content": ans.content,
            "trustCount": ans.trust_count,
            "isTrustedByMe": user_uid in ans.voted_user_ids,
            "createdAt": ans.created_at,
        })
        
    post_u = user_dict.get(post.author_id)
    post_author_resp = {
        "id": post.author_id,
        "nickname": post_u.nickname if post_u else "크라우디언",
        "trustCount": post_u.stats.trust if post_u else 0,
        "level": post_u.stats.level if post_u else 1,
    }

    return {
        "id": str(post.id),
        "title": post.title,
        "content": post.content,
        "isSos": post.is_sos,
        "category": post.category,
        "bounty": post.bounty,
        "author": post_author_resp,
        "answerCount": post.answer_count,
        "createdAt": post.created_at,
        "answers": answer_responses,
    }


async def submit_archive_answer(user: User, post_id: str, content: str) -> str:
    """질문에 답변을 작성합니다."""
    try:
        post = await archive_repo.get_by_id(post_id)
    except Exception:
        raise ValueError("유효하지 않은 Post ID입니다.")
        
    if not post:
        raise ValueError("질문 글을 찾을 수 없습니다.")
        
    answer = await archive_answer_repo.create(obj_in={
        "post_id": post_id,
        "author_id": user.uid,
        "content": content,
    })
    
    # 캐싱용 answer_count 증가
    post.answer_count += 1
    post.updated_at = datetime.now(timezone.utc)
    await archive_repo.update(db_obj=post, obj_in={"answer_count": post.answer_count, "updated_at": post.updated_at})
    
    return str(answer.id)


async def toggle_trust_vote(user: User, answer_id: str) -> dict:
    """답변에 신뢰함(투표)을 토글합니다."""
    try:
        answer = await archive_answer_repo.get(ObjectId(answer_id))
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
