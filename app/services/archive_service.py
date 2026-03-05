# app/services/archive_service.py

from datetime import datetime, timezone
from bson import ObjectId

from app.models.user import User
from app.models.archive import ArchivePost, ArchiveAnswer
from app.models.academy import KnowledgeCard


async def create_archive_post(user: User, title: str, content: str, is_sos: bool = False, category: str = "general", bounty: int = 0) -> str:
    """새로운 지식 도서관 질문을 등록합니다."""
    post = ArchivePost(
        title=title,
        content=content,
        is_sos=is_sos,
        category=category,
        bounty=bounty,
        author_id=user.uid,
    )
    await post.insert()
    return str(post.id)


async def get_archive_list(sort: str) -> list[ArchivePost]:
    """질문 목록을 조회합니다."""
    # sort param (latest | popular | bounty | needed)
    sort_query = []
    if sort == "popular":
        # 인기순 (구현상 답변이 많은 순)
        sort_query = [("answer_count", -1), ("created_at", -1)]
    elif sort == "bounty":
        # 현상금 순
        sort_query = [("bounty", -1), ("created_at", -1)]
    elif sort == "needed":
        # 답변이 적은 순 (답변 대기)
        sort_query = [("answer_count", 1), ("created_at", -1)]
    else:
        # 기본 최신순
        sort_query = [("created_at", -1)]
        
    posts = await ArchivePost.find().sort(*sort_query).to_list()
    return posts


async def get_archive_post_detail(post_id: str, user_uid: str) -> dict:
    """질문 상세 정보와 상위 답변들을 가져옵니다."""
    try:
        post = await ArchivePost.get(ObjectId(post_id))
    except Exception:
        raise ValueError("유효하지 않은 Post ID입니다.")
        
    if not post:
        raise ValueError("질문 글을 찾을 수 없습니다.")
        
    # 답변 조회 (가장 신뢰를 많이 받은 순)
    answers = await ArchiveAnswer.find(
        ArchiveAnswer.post_id == post_id
    ).sort([("trust_count", -1)]).to_list()
    
    from beanie.operators import In
    author_ids = list(set([ans.author_id for ans in answers] + [post.author_id]))
    users = await User.find(In(User.uid, author_ids)).to_list()
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
        post = await ArchivePost.get(ObjectId(post_id))
    except Exception:
        raise ValueError("유효하지 않은 Post ID입니다.")
        
    if not post:
        raise ValueError("질문 글을 찾을 수 없습니다.")
        
    # 동일 유저가 여러 답변을 달아도 되지만, 중복 체크 등 방어로직 추가 가능.
        
    answer = ArchiveAnswer(
        post_id=post_id,
        author_id=user.uid,
        content=content,
    )
    await answer.insert()
    
    # 캐싱용 answer_count 증가
    post.answer_count += 1
    post.updated_at = datetime.now(timezone.utc)
    await post.save()
    
    return str(answer.id)


async def toggle_trust_vote(user: User, answer_id: str) -> dict:
    """답변에 신뢰함(투표)을 토글합니다."""
    try:
        answer = await ArchiveAnswer.get(ObjectId(answer_id))
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
        
    await answer.save()
    
    # 신뢰도 보상 및 특별 로직 (trust_count == 10 달성 최초 1회 등)
    if is_trusted and answer.trust_count == 10:
        # 해당 답변 작성자의 신뢰도 스탯 증가 등의 보상을 주거나,
        # KnowledgeCard로 자동 승격
        await _promote_to_knowledge_card(answer)
        
        # 글 작성자에게 스탯 보상 (예시)
        author = await User.find_one(User.uid == answer.author_id)
        if author:
            author.stats.trust += 5
            await author.save()

    return {
        "isTrusted": is_trusted,
        "trustCount": answer.trust_count,
    }


async def _promote_to_knowledge_card(answer: ArchiveAnswer):
    """신뢰도 10 달성 시 Golden Dataset용 지식카드로 만드는 내부 로직."""
    try:
        post = await ArchivePost.get(ObjectId(answer.post_id))
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
