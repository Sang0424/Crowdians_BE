# app/api/v1/endpoints/chat.py

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.security import get_current_user, get_current_user_optional
from app.models.chat import ChatConversation
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatSendResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatUnlikeRequest,
    ChatUnlikeResponse,
    ChatSosRequest,
    ChatSosResponse,
)
from app.services.chat_service import (
    send_chat_message,
    clear_chat_history,
    delete_chat_message,
    get_or_create_conversation,
    generate_summary_for_archive,
    send_guest_chat_message,
)
from app.services.archive_service import create_archive_post

router = APIRouter()


# ══════════════════════════════════════
# POST /chat/message — 채팅 전송
# ══════════════════════════════════════

@router.post(
    "/chat/message",
    response_model=ChatSendResponse,
    summary="채팅 메시지 전송",
    description="AI에게 메시지를 전송하고 스탯(Stamina, EXP 등)을 계산하여 응답합니다.",
)
async def send_message(
    request: ChatMessageRequest,
    current_user: User | None = Depends(get_current_user_optional),
):
    try:
        if current_user is None:
            result = await send_guest_chat_message(request.content)
            return ChatSendResponse(**result)
            
        result = await send_chat_message(current_user, request.content)
        return ChatSendResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

@router.post("/chat/guest-message", response_model=ChatSendResponse, summary="게스트 채팅 메시지 전송", description="AI에게 메시지를 전송하고 스탯(Stamina, EXP 등)을 계산하여 응답합니다.")
async def send_guest_message(
    request: ChatMessageRequest,
):
    try:
        result = await send_guest_chat_message(request.content)
        return ChatSendResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ══════════════════════════════════════
# GET /chat/history — 채팅 내역 조회
# ══════════════════════════════════════

@router.get(
    "/chat/history",
    response_model=ChatHistoryResponse,
    summary="채팅 내역 조회",
    description="현재 활성화된 대화 세션의 메시지 목록을 가져옵니다.",
)
async def get_chat_history(
    current_user: User | None = Depends(get_current_user_optional),
    conversationId: str | None = Query(None, description="대화 세션 ID (생략 시 최신 세션)"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
):
    if current_user is None:
        return ChatHistoryResponse(conversationId="guest", messages=[])
        
    # 여기서는 간단히 최신 세션 전체 메시지를 반환합니다.
    conv = await get_or_create_conversation(current_user.uid)
    
    # Pagination
    start = max(0, len(conv.messages) - (page * limit))
    end = max(0, len(conv.messages) - ((page - 1) * limit))
    
    # 시간 역순 또는 순방향 조절 (여기서는 최신이 뒤에 있으므로 start:end 슬라이싱 후 반환)
    # 프론트엔드 편의를 위해 오래된 메시지가 먼저 나오도록 (시간 순) 정렬 유지
    items = conv.messages[start:end] if start < end else []
    
    msg_responses = [
        ChatMessageResponse(role=msg.role, content=msg.content, createdAt=msg.created_at)
        for msg in items
    ]
    
    return ChatHistoryResponse(
        conversationId=str(conv.id),
        messages=msg_responses,
    )


# ══════════════════════════════════════
# DELETE /chat/history — 채팅 초기화
# ══════════════════════════════════════

@router.delete(
    "/chat/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="채팅 내역 초기화",
    description="유저의 전체 대화 내역을 지우고 새로 시작합니다.",
)
async def delete_history(
    current_user: User = Depends(get_current_user),
):
    await clear_chat_history(current_user.uid)


# ══════════════════════════════════════
# DELETE /chat/message — 개별 메시지 삭제
# ══════════════════════════════════════

@router.delete(
    "/chat/message",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="단일 채팅 메시지 삭제",
)
async def delete_single_message(
    index: int = Query(..., description="삭제할 메시지의 배열 내 위치"),
    current_user: User = Depends(get_current_user),
):
    try:
        await delete_chat_message(current_user.uid, index)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ══════════════════════════════════════
# POST /chat/unlike — 불만족 답변 신고 (Teach DB 연동)
# ══════════════════════════════════════

@router.post(
    "/chat/unlike",
    response_model=ChatUnlikeResponse,
    summary="답변 불만족 신고 (Teach)",
    description="마음에 들지 않는 AI 답변을 신고하여 아카데미 지식의뢰로 등록(예정)합니다.",
)
async def unlike_message(
    request: ChatUnlikeRequest,
    current_user: User = Depends(get_current_user),
):
    title, content = await generate_summary_for_archive(
        uid=current_user.uid,
        text_context=f"불만족 답변(인덱스 {request.messageIndex}) 내역을 바탕으로 더 나은 답변을 위한 질문 작성",
        is_sos=False
    )
    
    await create_archive_post(
        user=current_user,
        title=title,
        content=content,
        category="qna",
        bounty=0,
        is_sos=False
    )
    
    return ChatUnlikeResponse(
        success=True,
        message=f"답변(인덱스 {request.messageIndex})이 신고되었습니다. 더 똑똑한 AI로 학습시키겠습니다.",
    )


# ══════════════════════════════════════
# POST /chat/sos — 지식 의뢰
# ══════════════════════════════════════

@router.post(
    "/chat/sos",
    response_model=ChatSosResponse,
    summary="마스터 지식 의뢰 (SOS)",
    description="30G를 지불하여 아카데미에 특별 지식 의뢰를 요청합니다.",
)
async def request_sos(
    request: ChatSosRequest,
    current_user: User = Depends(get_current_user),
):
    if current_user.stats.gold < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="골드가 부족합니다. (30G 필요)",
        )
    
    current_user.stats.gold -= 30
    await current_user.save()
    
    title, content = await generate_summary_for_archive(
        uid=current_user.uid,
        text_context=request.question,
        is_sos=True
    )
    
    # 지식 의뢰 데이터를 ArchivePost에 저장 (카테고리: sos)
    await create_archive_post(
        user=current_user,
        title=title,
        content=content,
        category="sos",
        bounty=30,
        is_sos=True
    )
    
    return ChatSosResponse(
        success=True,
        goldConsumed=30,
        message="지식 의뢰가 성공적으로 접수되었습니다. (30G 차감)",
    )
