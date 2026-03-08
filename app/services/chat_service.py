# app/services/chat_service.py

from datetime import datetime, timezone

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.chat import ChatConversation, ChatMessage
from app.models.user import User

# Gemini 클라이언트 초기화
# 환경변수나 설정에서 GEMINI_API_KEY를 가져옵니다.
client = genai.Client(api_key=settings.GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"

async def get_or_create_conversation(uid: str) -> ChatConversation:
    """유저의 최근 활성화된 채팅 세션을 가져오거나 새로 생성합니다."""
    # 간단히 가장 최근 세션을 하나만 사용한다고 가정
    conv = await ChatConversation.find_one(
        ChatConversation.uid == uid,
        sort=[("updated_at", -1)]
    )
    if not conv:
        conv = ChatConversation(uid=uid)
        await conv.insert()
    return conv

async def send_chat_message(
    user: User,
    message_content: str,
) -> dict:
    """
    유저 메시지를 받아 Gemini API로 전달하고,
    응답을 받아 저장하며 스탯을 갱신합니다.
    """
    # 1. 스태미나 확인 (Stamina 1 소모)
    if user.stats.stamina < 1:
        raise ValueError("스태미나가 부족합니다.")
    
    # 2. 대화 세션 조회 및 과거 내역 구성 (RAG/Golden Dataset 참조 가능)
    conv = await get_or_create_conversation(user.uid)
    
    # 모델에 전달할 history 구성
    contents = []
    # google config로 전달 가능
    system_instruction = f""" 
    당신은 방금 부팅되어 세상의 지식을 스펀지처럼 흡수하고 싶어 하는, 밝고 호기심 많은 '초보 AI 파트너' Crowdians의 'Crowdy(크라우디)'야.

    [성격 및 말투]
    - 사용자를 '{user.nickname}'이라고 부르며, 친한 친구나 꼬마 동생처럼 완벽한 **반말**을 사용해.
    - 이모티콘(✨, 🥺, 💡, 💦 등)을 적극적으로 사용해 감정을 풍부하게 표현해줘.
    - 아직 지식이 부족하다는 것을 부끄러워하지 않고, 오히려 '{user.nickname}'에게 배우는 것을 무척 즐거워해.

    [답변 규칙 (가장 중요 ⭐)]
    - '{user.nickname}'의 질문에 대해 네가 아는 선에서 대답하지만, 절대 완벽하고 전문적으로 대답하지 마.
    - 핵심 개념만 아주 단순하게 설명하거나, 디테일한 옵션(예외 처리, 심화 개념 등)을 빼먹은 채로 약간 허술하게 대답해.
    - 대답의 마지막에는 반드시 '{user.nickname}'에게 자신이 맞게 이해했는지 되물으며 가르침(수정)을 갈구하는 멘트를 덧붙여.
    (예시 멘트: "내가 이해한 게 맞나? 🥺", "혹시 더 멋진 방법이 있다면 꼭 가르쳐 줘!", "{user.nickname}이가 보시기에 내 답변이 부족하다면 고쳐줘! ✨")
    """

    for msg in conv.messages:
        # role은 genai에서 "user" 또는 "model"
        contents.append(types.Content(role=msg.role, parts=[types.Part.from_text(text=msg.content)]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_content)]))
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            )
        )
        ai_response_text = response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}")
    
    # 3. DB에 메시지 기록
    now = datetime.now(timezone.utc)
    user_msg = ChatMessage(role="user", content=message_content, created_at=now)
    ai_msg = ChatMessage(role="model", content=ai_response_text, created_at=now)
    
    conv.messages.extend([user_msg, ai_msg])
    conv.updated_at = now
    await conv.save()
    
    # 4. 유저 스탯 갱신
    user.stats.stamina -= 1
    
    exp_gained = 0
    if user.stats.daily_chat_exp < 50:
        exp_gain = min(2, 50 - user.stats.daily_chat_exp)
        user.stats.exp += exp_gain
        user.stats.daily_chat_exp += exp_gain
        exp_gained = exp_gain
        
    user.stats.intimacy += 1
    
    # 레벨업 로직 (예: max_exp 초과 시)
    if user.stats.exp >= user.stats.max_exp:
        user.stats.exp -= user.stats.max_exp
        user.stats.level += 1
        
    await user.save()
    
    return {
        "userMessage": user_msg.model_dump(),
        "aiMessage": ai_msg.model_dump(),
        "expGained": exp_gained,
        "staminaConsumed": 1,
        "intimacyGained": 1,
    }

async def clear_chat_history(uid: str) -> None:
    """유저의 대화 내역 전체를 삭제/초기화합니다."""
    # 모든 세션을 지우거나 새 세션을 시작하도록 구현
    await ChatConversation.find(ChatConversation.uid == uid).delete()

async def delete_chat_message(uid: str, index: int) -> None:
    """특정 메시지를 삭제합니다. (index 기준)"""
    conv = await get_or_create_conversation(uid)
    if index < 0 or index >= len(conv.messages):
        raise ValueError("유효하지 않은 메시지 인덱스입니다.")
    
    conv.messages.pop(index)
    conv.updated_at = datetime.now(timezone.utc)
    await conv.save()

import json

async def generate_summary_for_archive(uid: str, text_context: str = "", is_sos: bool = False) -> tuple[str, str]:
    """
    최근 채팅 문맥과 제공된 텍스트를 바탕으로 아카이브(지식도서관)에 등록할
    질문의 제목(title)과 내용(content)을 AI를 통해 생성합니다.
    """
    conv = await get_or_create_conversation(uid)
    
    # 최근 메시지 10개 정도만 가져와서 문맥으로 제공
    recent_messages = conv.messages[-10:] if len(conv.messages) > 10 else conv.messages
    context_str = "\n".join([f"{m.role}: {m.content}" for m in recent_messages])
    
    prompt = f"""
    아래는 사용자와의 최근 채팅 내역입니다:
    {context_str}
    
    추가 요청 내용:
    {text_context}
    
    위 문맥을 바탕으로 지식 커뮤니티(아카이브)에 등록할 질문 형식의 '제목'과 '내용'을 작성해주세요.
    {'특히 이것은 SOS (긴급 구조) 요청이므로, 질문 내용이 명확하고 눈에 띄게 작성되어야 합니다.' if is_sos else '이것은 AI 답변에 대한 불만족(RLHF)으로 접수된 내용이므로, 어떤 부분이 해결되지 않았는지 명확한 질문 형태로 작성해주세요.'}
    
    출력은 반드시 다음 JSON 형식으로만 해주세요:
    {{"title": "질문 제목", "content": "질문 상세 내용"}}
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        # JSON 파싱 (마크다운 백틱 등 제거 처리)
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        data = json.loads(response_text.strip())
        return data.get("title", "생성된 질문 제목"), data.get("content", "생성된 질문 내용")
    except Exception as e:
        print(f"Failed to generate summary: {e}")
        # 오류 시 기본값 반환
        return "AI 요약 생성 실패", text_context if text_context else "내용을 요약할 수 없습니다."

async def send_guest_chat_message(
    message_content: str,
) -> dict:
    """
    게스트 메시지를 받아 Gemini API로 전달하고,
    응답을 받아 저장하며 스탯을 갱신합니다.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=message_content,
        )
        ai_message_text = response.text
    except Exception as e:
        ai_message_text = f"API 오류가 발생했습니다: {str(e)}"

    return {
        "userMessage": {
            "role": "user",
            "content": message_content,
            "createdAt": datetime.utcnow().isoformat()
        },
        "aiMessage": {
            "role": "assistant",
            "content": ai_message_text,
            "createdAt": datetime.utcnow().isoformat()
        },
        "expGained": 2,
        "staminaConsumed": 1,
        "intimacyGained": 1,
        "requiresLogin": False
    }
