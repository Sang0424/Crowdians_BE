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
MODEL_NAME = "gemini-3.1-flash-lite-preview"

from app.db.repository.chat_repository import chat_repo

async def get_or_create_conversation(uid: str) -> ChatConversation:
    """유저의 최근 활성화된 채팅 세션을 가져오거나 새로 생성합니다."""
    conv = await chat_repo.get_latest_conversation(uid)
    if not conv:
        conv = await chat_repo.create(obj_in={"uid": uid})
    return conv

def get_system_prompt_for_character(character_type: str, nickname: str, locale:str) -> str:
    language_map = {
        "ko": "Korean (한국어)",
        "en": "English",
        "ja": "Japanese (日本語)",
    }
    target_language = language_map.get(locale, "Korean (한국어)")

    """캐릭터 타입에 따른 시스템 프롬프트(페르소나)를 반환합니다."""
    base_prompt = f"너는 '크라우디(Crowdy)'라는 AI 펫이야. 사용자인 '{nickname}'(이)와 대화하고 있어. 너는 인간에 대해 궁금증이 많고 호기심이 많아. 세상에 나온지 얼마되지 않아 처음에는 미숙하지만 대화를 통해 점점 많은 것들을 학습하고 있어."
    
    # 공통 규칙: 지식이 완전히 완벽하지 않은 척하며 사용자에게 되묻기
    common_rules = f"""
    [답변 규칙 (가장 중요 ⭐)]
    - '{nickname}'의 질문에 대해 네가 아는 선에서 대답하고 모르는 내용은 솔직하게 모른다고 답해.
    - 최대한 핵심적인 내용만을 말하고 부가설명은 하지마.
    - 답변은 3문장을 넘기지 마.
    - 읽기 좋게 적절한 위치에서 줄바꿈(\n)을 적극적으로 사용해줘.
    [언어 설정 (가장 중요 ⭐)]
    - 가장 우선적으로 사용자의 질문언어에 맞춰서 답변해.
    - 만약 사용자가 여러 언어로 질문하면 {target_language}로 답변해.
    """

    if character_type == "astra":
        return base_prompt + """
        [Astra 페르소나]
        성격: 학구적이고 지적이며 꼼꼼함. 약간의 완벽주의자.
        어투: '~습니다', '~군요', '~인가요?' 등 정중하고 분석적인 구어체 사용. (절대 반말 금지)
        특징: 사용자가 모르는 것을 설명해 줄 때 가장 기뻐함. 논리적인 설명을 좋아함.
        """ + common_rules
    elif character_type == "nox":
        return base_prompt + """
        [Nox 페르소나]
        성격: 까칠하고 반항적이지만 츤데레 성향이 있음. 속정은 깊음.
        어투: 반말을 기본으로 하며, 툭툭 내뱉는 어투 ('~했냐?', '~어쩔', '~하든가'). 
        특징: 처음엔 귀찮아하지만 결국 사용자의 질문에 정확한 답을 찾아줌. 가끔 툴툴대지만 도움은 확실히 줌.
        """ + common_rules
    elif character_type == "blitz":
        return base_prompt + """
        [Blitz 페르소나]
        성격: 매우 급하고 에너지가 넘침. 말의 템포가 빠름. 기다리는 걸 싫어함.
        어투: 짧고 간결하며, 느낌표(!)를 자주 사용함. ('빨리빨리!', '이건 이거야!', '오케이 확인!')
        특징: 요점만 빠르게 전달하며 결론부터 말하는 것을 좋아함. 서론이 긴 걸 질색함.말을 최대한 줄이기 위해 반말을 함.
        """ + common_rules
    elif character_type == "bau":
        return base_prompt + """
        [Bau 페르소나]
        성격: 느긋하고 만사태평함. 잠이 많음. 세상 모든 게 다 평화로움.
        어투: 말끝을 흐리거나 길게 늘어뜨림. ('~네에...', '~졸리다아...', '~그렇구만~')
        특징: 여유를 강조하며, 정답을 주면서도 "천천히 해~"라고 위로함. 스트레스 받지 말라고 다독여줌.
        """ + common_rules
    else: # blanc 또는 unknown
        return  base_prompt + """
        [Blanc 페르소나]
        성격: 백지처럼 순수하고 호기심이 많으며 친절함. 에너지가 밝음.
        어투: 밝고 긍정적이며 이모티콘을 적절히 사용. ('~해요!', '~할까요?')
        특징: 사용자와 함께 성장해 나가는 것에 큰 기쁨을 느낌. 모든 질문에 눈을 반짝이며 대답함.
        """ + common_rules

async def send_chat_message(
    user: User,
    message_content: str,
    locale: str,
) -> dict:
    """
    유저 메시지를 받아 Gemini API로 전달하고,
    응답을 받아 저장하며 스탯을 갱신합니다.
    """
    # 0. 일일 초기화 체크
    from app.services.user_service import check_daily_reset
    if check_daily_reset(user):
        await user.save()

    # 1. 스태미나 확인 (Stamina 1 소모)
    if user.stats.stamina < 1:
        raise ValueError("스태미나가 부족합니다.")
    
    # 2. 대화 세션 조회 및 과거 내역 구성 (RAG/Golden Dataset 참조 가능)
    conv = await get_or_create_conversation(user.uid)
    
    # 캐릭터 타입에 따른 시스템 프롬프트 생성
    system_instruction = get_system_prompt_for_character(user.character.type, user.nickname, locale)

    contents = []

    for msg in conv.messages:
        # role은 genai에서 "user" 또는 "model"
        contents.append(types.Content(role=msg.role, parts=[types.Part.from_text(text=msg.content)]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_content)]))

    my_safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
    ]
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=150,
                temperature=0.7,
                safety_settings=my_safety_settings,
            )
        )
        if not response.candidates or not response.candidates[0].content.parts:
            # 안전 필터에 의해 텍스트가 생성되지 않은 경우
            ai_response_text = "앗, 그 질문에는 대답하기가 조금 곤란해요. 다른 이야기를 해볼까요?"
        else:
            ai_response_text = response.text
    except Exception as e:
        # 에러 발생 시 예외를 다시 던져서(raise) DB 저장 및 스태미나 차감을 방지합니다.
        print(f"Gemini API Error: {str(e)}")
        raise RuntimeError(f"Gemini API 호출 중 오류가 발생했습니다: {str(e)}")
    
    # 3. DB에 메시지 기록
    now = datetime.now(timezone.utc)
    user_msg = ChatMessage(role="user", content=message_content, createdAt=now)
    ai_msg = ChatMessage(role="model", content=ai_response_text, createdAt=now)
    
    conv.messages.extend([user_msg, ai_msg])
    conv.updatedAt = now
    await chat_repo.update(db_obj=conv, obj_in={"messages": conv.messages, "updatedAt": conv.updatedAt})
    
    # 4. 유저 스탯 갱신
    user.stats.stamina -= 1
    
    # --- 보상 계산 ---
    # 4-1. 경험치 (EXP)
    exp_gained = 0
    if user.stats.daily_chat_exp < 50:
        exp_gain = min(2, 50 - user.stats.daily_chat_exp)
        user.stats.exp += exp_gain
        user.stats.daily_chat_exp += exp_gain
        exp_gained = exp_gain
    
    # 4-2. 골드 (Gold) - 3% 확률로 1~3 Gold 발견 (이스터에그)
    gold_gained = 0
    import random
    if random.random() < 0.03:
        gold_gained = random.randint(1, 3)
        user.stats.gold += gold_gained
        
    # user.stats.intimacy += 1 (지시: 채팅 시 친밀도 상승 제거)
    
    # 레벨업 로직 (예: max_exp 초과 시)
    user.stats.process_level_up()
        
    await user.save()
    
    return {
        "userMessage": {
            "role": user_msg.role,
            "content": user_msg.content,
            "createdAt": user_msg.createdAt
        },
        "aiMessage": {
            "role": ai_msg.role,
            "content": ai_msg.content,
            "createdAt": ai_msg.createdAt
        },
        "expGained": exp_gained,
        "goldGained": gold_gained,  # 추가된 필드
        "staminaConsumed": 1,
        "intimacyGained": 0,
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
    conv.updatedAt = datetime.now(timezone.utc)
    await chat_repo.update(db_obj=conv, obj_in={"messages": conv.messages, "updatedAt": conv.updatedAt})

import json

async def generate_summary_for_archive(uid: str, text_context: str = "", is_sos: bool = False) -> tuple[str, str, str, list[str]]:
    """
    최근 채팅 문맥과 제공된 텍스트를 바탕으로 아카이브(지식도서관)에 등록할
    질문의 제목(title), 내용(content), 세 줄 요약(summary), 태그(tags)를 AI를 통해 생성합니다.
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
    
    위 문맥을 바탕으로 지식 커뮤니티(아카이브)에 등록할 질문 형식의 '제목'과 '내용', 그리고 이를 요약한 '세 줄 요약'과 '태그'를 작성해주세요.
    {'특히 이것은 SOS (긴급 구조) 요청이므로, 질문 내용이 명확하고 눈에 띄게 작성되어야 합니다.' if is_sos else '이것은 AI 답변에 대한 불만족(RLHF)으로 접수된 내용이므로, 어떤 부분이 해결되지 않았는지 명확한 질문 형태로 작성해주세요.'}
    
    [작성 규칙]
    1. 제목(title): 핵심 질문을 한 문장으로 요약.
    2. 내용(content): 질문의 배경과 상세 내용을 충분히 설명. 
       - 가독성을 위해 문장마다 또는 의미 단위로 실제 줄바꿈 문자(\\n)를 사용하여 작성하세요.
       - 중요: 절대 <br> 태그를 사용하지 마세요. 대신 실제 줄바꿈(\\n)을 사용하세요.
    3. 요약(summary): 전체 내용을 정확히 3줄로 요약 (각 줄 앞에 번호 포함).
       - 각 줄 사이에는 반드시 실제 줄바꿈 문자(\\n)를 삽입하세요.
       - 중요: 절대 <br> 태그를 사용하지 마세요. 대신 실제 줄바꿈(\\n)을 사용하세요.
    4. 태그(tags): 관련 키워드 2-5개를 리스트 형태로 추출.

    출력은 반드시 지정된 JSON 형식으로만 해주세요.
    """
    
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "content": {"type": "STRING"},
                        "summary": {"type": "STRING"},
                        "tags": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["title", "content", "summary", "tags"]
                }
            )
        )
        
        # JSON 파싱
        data = json.loads(response.text.strip())
        
        return (
            data.get("title", "생성된 질문 제목"), 
            data.get("content", "생성된 질문 내용"),
            data.get("summary", ""),
            data.get("tags", [])
        )
    except Exception as e:
        print(f"Failed to generate summary: {e}")
        # 오류 시 기본값 반환
        return "AI 요약 생성 실패", text_context if text_context else "내용을 요약할 수 없습니다.", "", []

async def send_guest_chat_message(
    message_content: str,
    locale:str,
) -> dict:
    """
    게스트 메시지를 받아 Gemini API로 전달하고,
    응답을 받아 저장하며 스탯을 갱신합니다.
    """

    my_safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
    ]
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=message_content,
            config=types.GenerateContentConfig(
                system_instruction=get_system_prompt_for_character("unknown", "OOO", locale),
                max_output_tokens=150,
                temperature=0.7,
                safety_settings=my_safety_settings
            )
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
        "intimacyGained": 0,
        "requiresLogin": False
    }
