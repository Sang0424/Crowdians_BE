# app/api/v1/endpoints/archive.py

from fastapi import APIRouter, Query, HTTPException, status

from app.core.security import CurrentUser
from app.models.user import User
from app.schemas.archive import (
    ArchivePostResponse,
    ArchivePostDetailResponse,
    ArchivePostRequest,
    ArchivePostSubmitResponse,
    ArchiveAnswerRequest,
    ArchiveAnswerSubmitResponse,
    TrustVoteResponse,
    PaginatedArchiveResponse,
)
from app.services.archive_service import (
    create_archive_post,
    get_archive_list,
    get_archive_post_detail,
    submit_archive_answer,
    toggle_trust_vote,
)
from app.core.exceptions import InsufficientResourceError, NotFoundError

router = APIRouter()


# ══════════════════════════════════════
# GET /archive — 지식 도서관 목록 조회 (페이지네이션)
# ══════════════════════════════════════

@router.get(
    "/archive",
    response_model=PaginatedArchiveResponse,
    summary="지식 도서관(Archive) 게시글 목록 (페이지네이션)",
    description="최신(latest), 인기(popular), 바운티(bounty), 답변대기(needed) 순 정렬 지원. page/size로 페이지네이션.",
)
async def get_archives(
    current_user: CurrentUser,
    sort: str = Query("latest", pattern="^(latest|popular|bounty|needed)$"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(10, ge=1, le=50, description="페이지당 아이템 수"),
):
    skip = (page - 1) * size
    posts, total_count = await get_archive_list(sort, skip=skip, limit=size)
    
    author_ids = list(set([p.author_id for p in posts]))
    from beanie.operators import In
    users = await User.find(In(User.uid, author_ids)).to_list()
    user_dict = {u.uid: u for u in users}

    items = []
    for p in posts:
        u = user_dict.get(p.author_id)
        author_resp = {
            "id": p.author_id,
            "nickname": u.nickname if u else "크라우디언",
            "trustCount": u.stats.trust if u else 0,
            "level": u.stats.level if u else 1,
        }
        items.append(
            ArchivePostResponse(
                id=str(p.id),
                title=p.title,
                content=p.content,
                isSos=p.is_sos,
                category=p.category,
                bounty=p.bounty,
                author=author_resp,
                answerCount=p.answer_count,
                createdAt=p.created_at,
            )
        )

    has_more = (skip + size) < total_count

    return PaginatedArchiveResponse(
        items=items,
        page=page,
        size=size,
        totalCount=total_count,
        hasMore=has_more,
    )


# ══════════════════════════════════════
# GET /archive/{id} — 지식 도서관 상세 조회
# ══════════════════════════════════════

@router.get(
    "/archive/{post_id}",
    response_model=ArchivePostDetailResponse,
    summary="질문글 및 답변 목록 상세 조회",
)
async def get_archive_detail(
    post_id: str,
    current_user: CurrentUser,
):
    try:
        detail_dict = await get_archive_post_detail(post_id, current_user.uid)
        return ArchivePostDetailResponse(**detail_dict)
    except ValueError as e:
        raise NotFoundError("게시글")


# ══════════════════════════════════════
# POST /archive — 질문 등록 (추가 구현)
# ══════════════════════════════════════

@router.post(
    "/archive",
    response_model=ArchivePostSubmitResponse,
    summary="새로운 지식 질문 등록",
    description="프론트엔드에서 유저가 직접 질문을 올릴 수 있도록 지원합니다.",
)
async def create_post(
    request: ArchivePostRequest,
    current_user: CurrentUser,
):
    if request.bounty > 0 and current_user.stats.gold < request.bounty:
        raise InsufficientResourceError("골드")
        
    try:
        if request.bounty > 0:
            current_user.stats.gold -= request.bounty
            from app.db.repository.user_repository import user_repo
            await user_repo.update(db_obj=current_user, obj_in={"stats": current_user.stats})
            
        post_id = await create_archive_post(
            current_user,
            title=request.title,
            content=request.content,
            category=request.category,
            bounty=request.bounty
        )
        return ArchivePostSubmitResponse(
            success=True,
            postId=post_id,
            message="질문이 지식 도서관에 성공적으로 등록되었습니다."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ══════════════════════════════════════
# POST /archive/{id}/answers — 답변 작성
# ══════════════════════════════════════

@router.post(
    "/archive/{post_id}/answers",
    response_model=ArchiveAnswerSubmitResponse,
    summary="질문에 대한 답변 달기",
)
async def create_answer(
    post_id: str,
    request: ArchiveAnswerRequest,
    current_user: CurrentUser,
):
    try:
        ans_id = await submit_archive_answer(current_user, post_id, request.content)
        return ArchiveAnswerSubmitResponse(
            success=True,
            answerId=ans_id,
            message="답변이 등록되었습니다."
        )
    except ValueError as e:
        raise NotFoundError("게시글")


# ══════════════════════════════════════
# POST /archive/answers/{answerId}/trust — 신뢰함 투표
# ══════════════════════════════════════

@router.post(
    "/archive/answers/{answer_id}/trust",
    response_model=TrustVoteResponse,
    summary="답변에 '신뢰함' 투표 (토글)",
    description="자신의 글이 아닌 답변에 투표하며, 토글 방식으로 동작합니다. 10회 도달 시 데이터셋 편입 로직이 작동될 수 있습니다.",
)
async def vote_trust(
    answer_id: str,
    current_user: CurrentUser,
):
    try:
        result = await toggle_trust_vote(current_user, answer_id)
        return TrustVoteResponse(
            success=True,
            isTrusted=result["isTrusted"],
            trustCount=result["trustCount"],
            message="신뢰함 상태가 전환되었습니다."
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
