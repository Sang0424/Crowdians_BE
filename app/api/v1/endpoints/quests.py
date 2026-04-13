# app/api/v1/endpoints/quests.py

from fastapi import APIRouter, HTTPException, status
from app.core.security import CurrentUser
from app.schemas.quest import (
    QuestCreate,
    QuestCreateResponse,
    QuestBookmarkToggleResponse
)
from app.services.quest_service import create_quest
from app.core.exceptions import DomainError

from app.schemas.quest import QuestAnswerRequest, QuestAnswerResponse
from app.services.quest_service import answer_quest

router = APIRouter()


@router.post(
    "",
    response_model=QuestCreateResponse,
    summary="직접 의뢰하기",
    status_code=status.HTTP_201_CREATED
)
async def post_quest(
    request: QuestCreate,
    current_user: CurrentUser
):
    try:
        quest_id = await create_quest(
            user=current_user,
            title=request.title,
            description=request.description,
            tags=request.tags,
            reward=request.reward,
            is_sos=request.is_sos,
            target_user_id=request.targetUserId
        )
        return QuestCreateResponse(
            success=True,
            questId=quest_id,
            message="의뢰가 성공적으로 등록되었습니다."
        )
    except DomainError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# @router.post(
#     "/{quest_id}/bookmark",
#     response_model=QuestBookmarkToggleResponse,
#     summary="의뢰 북마크 토글"
# )
# async def toggle_bookmark(
#     quest_id: str,
#     current_user: CurrentUser
# ):
#     try:
#         is_bookmarked = await toggle_quest_bookmark(current_user, quest_id)
#         return QuestBookmarkToggleResponse(
#             success=True,
#             isBookmarked=is_bookmarked,
#             message="북마크 상태가 전환되었습니다."
#         )
#     except DomainError as e:
#         raise HTTPException(status_code=e.status_code, detail=e.message)
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(e)
#         )

@router.post(
    "/answer",
    response_model=QuestAnswerResponse,
    summary="의뢰(퀘스트) 답변하기"
)
async def post_quest_answer(
    request: QuestAnswerRequest,
    current_user: CurrentUser
):
    try:
        await answer_quest(
            user=current_user,
            quest_id=request.questId,
            content=request.content
        )
        return QuestAnswerResponse(success=True, message="답변이 성공적으로 전송되었습니다.")
    except DomainError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )