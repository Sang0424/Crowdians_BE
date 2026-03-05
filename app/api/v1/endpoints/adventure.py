# app/api/v1/endpoints/adventure.py

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.adventure import (
    AdventureSessionResponse,
    AdventureNodeResponse,
    AdventureSelectRequest,
    AdventureSelectResponse,
    AdventureContinueResponse,
)
from app.services.adventure_service import (
    start_adventure,
    select_adventure_node,
    continue_adventure,
)

router = APIRouter()


# ══════════════════════════════════════
# POST /adventures/start — 모험 시작
# ══════════════════════════════════════

@router.post(
    "/adventures/start",
    response_model=AdventureSessionResponse,
    summary="새로운 모험 시작",
    description="스태미나 1을 지불하고 1층부터 시작하는 새로운 탐험 세션을 생성합니다.",
)
async def start_new_adventure(
    current_user: User = Depends(get_current_user),
):
    try:
        session = await start_adventure(current_user)
        
        current_node = session.nodes[-1]
        
        node_response = AdventureNodeResponse(
            depth=current_node.depth,
            eventType=current_node.event_type,
            title=current_node.title,
            description=current_node.description,
            choices=[{"id": c.id, "text": c.text} for c in current_node.choices],
            isCleared=current_node.is_cleared,
        )
        
        return AdventureSessionResponse(
            sessionId=str(session.id),
            hp=session.hp,
            currentDepth=session.current_depth,
            maxDepth=session.max_depth,
            status=session.status,
            currentNode=node_response,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ══════════════════════════════════════
# POST /adventures/{session_id}/select — 선택지 고르기
# ══════════════════════════════════════

@router.post(
    "/adventures/{session_id}/select",
    response_model=AdventureSelectResponse,
    summary="현재 층(노드)에서의 행동 선택",
    description="선택에 따른 확률(Courage 스탯 기준)을 굴려 성공/실패 여부와 보상, 체력 감소를 결정합니다.",
)
async def select_choice(
    session_id: str,
    request: AdventureSelectRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result_dict = await select_adventure_node(current_user, session_id, request.choiceId)
        return AdventureSelectResponse(**result_dict)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ══════════════════════════════════════
# POST /adventures/{session_id}/continue — 다음 층 이동
# ══════════════════════════════════════

@router.post(
    "/adventures/{session_id}/continue",
    response_model=AdventureContinueResponse,
    summary="다음 깊이(층)로 이동",
    description="이벤트를 해결한 후 다음 층으로 넘어가 새로운 노드를 스폰합니다.",
)
async def goto_next_depth(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        result_dict = await continue_adventure(current_user, session_id)
        
        node_info = result_dict.get("nextNode")
        parsed_node = None
        if node_info:
            parsed_node = AdventureNodeResponse(**node_info)
            
        return AdventureContinueResponse(
            success=result_dict["success"],
            nextNode=parsed_node,
            status=result_dict["status"],
            message=result_dict["message"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
