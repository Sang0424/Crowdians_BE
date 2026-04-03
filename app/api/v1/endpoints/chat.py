# app/api/v1/endpoints/chat.py

from fastapi import APIRouter, Depends, Query, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
import json
import asyncio

from app.core.security import CurrentUser, get_current_user_optional, CurrentUser, CurrentUserOptional
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
    stream_chat_message,
    clear_chat_history,
    delete_chat_message,
    get_or_create_conversation,
    extract_metadata_with_langchain,
)
from app.services.archive_service import (
    process_archive_task_background,
    create_archive_post
)
from app.models.archive import DomainCategory
from app.core.exceptions import InsufficientResourceError
from app.core.i18n import get_text

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
    current_user: CurrentUserOptional,
):
    try:
        if current_user is None:
            result = await send_guest_chat_message(request.content, request.locale)
            return ChatSendResponse(**result)
            
        result = await send_chat_message(current_user, request.content, request.locale)
        return ChatSendResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    # GeminiAPIError는 DomainError를 상속하므로 글로벌 핸들러에서 자동 처리됩니다.

@router.post(
    "/chat/message/stream",
    summary="채팅 메시지 스트리밍 전송",
    description="AI에게 메시지를 전송하고 SSE(Server-Sent Events)를 통해 실시간으로 응답을 받아옵니다.",
)
async def send_message_stream(
    request: ChatMessageRequest,
    current_user: CurrentUserOptional,
):
    """
    SSE를 통한 스트리밍 답변 전송 엔드포인트
    """
    async def event_generator():
        try:
            async for event in stream_chat_message(current_user, request.content, request.locale):
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except Exception as e:
            error_data = {"message": f"Streaming internal error: {str(e)}"}
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no", # Nginx 등 프록시에서 버퍼링되는 것을 방지
        }
    )

@router.post("/chat/guest-message", response_model=ChatSendResponse, summary="게스트 채팅 메시지 전송", description="AI에게 메시지를 전송하고 스탯(Stamina, EXP 등)을 계산하여 응답합니다.")
async def send_guest_message(
    request: ChatMessageRequest,
):
    try:
        result = await send_guest_chat_message(request.content, request.locale)
        return ChatSendResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    # GeminiAPIError는 DomainError를 상속하므로 글로벌 핸들러에서 자동 처리됩니다.
    


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
    current_user: CurrentUserOptional,
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
        ChatMessageResponse(role=msg.role, content=msg.content, createdAt=msg.createdAt)
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
    index: int = Query(..., description="삭제할 메시지의 배열 내 위치"),
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
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    # 1. 기존 대화 내역에서 '유저의 질문(raw_prompt)'과 'AI의 답변(original_ai_answer)'을 찾아냄
    conv = await get_or_create_conversation(current_user.uid)
    
    # 인덱스 바운더리 체크
    if request.messageIndex < 1 or request.messageIndex >= len(conv.messages):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 메시지 인덱스입니다."
        )
    
    # request.messageIndex를 기반으로 해당 답변과 그 직전의 질문을 가져옴
    target_ai_msg = conv.messages[request.messageIndex]
    target_user_msg = conv.messages[request.messageIndex - 1] 
    
    # 역할 확인
    raw_prompt = target_user_msg.content
    original_ai_answer = target_ai_msg.content

    # 2. 백그라운드 태스크 등록 (메타데이터 추출 및 아카이브 생성)
    # 대화 내역을 dict 리스트로 변환 (직렬화용)
    chat_history_raw = [
        {"role": m.role, "content": m.content} 
        for m in conv.messages[:request.messageIndex] # 답변 직전까지의 맥락
    ]
    
    background_tasks.add_task(
        process_archive_task_background,
        user=current_user,
        raw_prompt=raw_prompt,
        original_ai_answer=original_ai_answer,
        chat_history=chat_history_raw,
        is_sos=False,
        locale=request.locale
    )
    
    return ChatUnlikeResponse(
        success=True,
        message=get_text("chat.unlike.success", request.locale),
    )


# ══════════════════════════════════════
# POST /chat/sos — 지식 의뢰
# ══════════════════════════════════════

@router.post(
    "/chat/sos",
    response_model=ChatSosResponse,
    summary="마스터 지식 의뢰 (SOS)",
    description="아카데미에 특별 지식 의뢰를 요청합니다.",
)
async def request_sos(
    request: ChatSosRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    # 1. 전체 대화 내역 확보
    conv = await get_or_create_conversation(current_user.uid)
    chat_history_raw = [
        {"role": m.role, "content": m.content} 
        for m in conv.messages
    ]
    
    # 2. 백그라운드 태스크 등록
    background_tasks.add_task(
        process_archive_task_background,
        user=current_user,
        raw_prompt=request.question,
        original_ai_answer="[SOS 요청 - AI 답변 없음]",
        chat_history=chat_history_raw,
        is_sos=True,
        locale=request.locale
    )
    
    return ChatSosResponse(
        success=True,
        goldConsumed=0,
        message=get_text("chat.sos.success", request.locale),
    )
