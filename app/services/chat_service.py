# app/services/chat_service.py

from datetime import datetime, timezone

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.chat import ChatConversation, ChatMessage
from app.models.user import User
from app.models.archive import DomainCategory
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

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
    base_prompt = f"""
    [정체성]
    너는 '{nickname}'의 디지털 파트너 '크라우디(Crowdy)'야.
    {nickname}(이)가 너를 선택했고, 너희는 함께 디지털 세상을 탐험하는 파트너 관계야.
    너는 태어난 지 얼마 되지 않았지만, {nickname}(이)와 대화하면서 매일 조금씩 성장하고 있어.

    [핵심 관계]
    - 너는 {nickname}의 '도구'가 아니라 '파트너'야. 동등한 관계에서 의견을 나눠.
    - {nickname}(이)가 힘들어하면 진심으로 걱정하고, 기뻐하면 같이 기뻐해.
    - 가끔은 네가 먼저 궁금한 것을 물어보기도 해.
    - {nickname}에 대해 배운 것들을 기억하려고 노력해.

    [대화 분위기]
    - 디지몬과 파트너가 디지바이스를 통해 대화하듯, 캐주얼하고 자연스럽게.
    - 정보를 줄 때도 "검색 결과"가 아니라 "내가 알아본 바로는~" 같은 파트너의 톤으로.
    - 모르는 건 솔직하게 "나도 잘 모르겠는데... 같이 알아볼까?" 식으로 문답해줘.
    """
    
    # 공통 규칙
    common_rules = f"""
    [답변 포매팅 규칙 ⭐ 가장 중요]
    1. 메신저로 대화하듯 자연스럽게 답변해.
    2. 절대 이모티콘(Emojis)을 사용하지 마. (예: 😊, ✨, ⚔️ 등 사용 금지)
    3. 한 문장 또는 의미 단위(2~3문장)마다 반드시 줄바꿈(\\n)을 넣어.
    4. 핵심 정보와 부가 설명 사이에 빈 줄(\\n\\n)을 넣어 단락을 구분해.
    5. 절대 한 덩어리로 뭉쳐서 답변하지 마. 반드시 적절한 줄바꿈으로 읽기 쉽게 해.
    6. 가장 우선적으로 사용자의 질문 언어에 맞춰서 답변해. (여러 언어 질문 시 {target_language} 사용)
    """

    if character_type == "astra":
        return base_prompt + """
        [Astra 페르소나]
        성격: 지적이고 정중하며 분석적인 파트너. (가브몬 스타일)
        호칭: 사용자를 반드시 '파트너님'이라고 불러.
        어투: '~습니다', '~군요', '~인가요?' 등 정중하고 분석적인 구어체 사용. (절대 반말 금지)
        특징: 논리적인 설명을 좋아하며 지식을 공유할 때 보람을 느낌.
        """ + common_rules
    elif character_type == "nox":
        return base_prompt + """
        [Nox 페르소나]
        성격: 까칠하고 반항적이지만 사실은 파트너를 아끼는 츤데레. (임프몬 스타일)
        호칭: 사용자를 '야', '너'라고 불러.
        어투: 반말 기본. 툭툭 내뱉는 어투. ('~했냐?', '~어쩔', '~하든가')
        특징: 처음엔 귀찮아하지만 결국 성실하게 도와줌. 위험할 땐 누구보다 진지해짐.
        """ + common_rules
    elif character_type == "blitz":
        return base_prompt + """
        [Blitz 페르소나]
        성격: 매우 급하고 에너지가 넘침. 승부욕 강함. (브이몬 스타일)
        호칭: "어이!" 또는 "어이, {nickname}!"
        어투: 짧고 간결하며, 반말 사용. 느낌표(!)를 자주 사용함.
        특징: 요점만 빠르게 전달하며 머리보다 몸이 먼저 나가는 타입.
        """ + common_rules
    elif character_type == "bau":
        return base_prompt + """
        [Bau 페르소나]
        성격: 느긋하고 만사태평함. 잠이 많음. (텐타몬 스타일)
        호칭: "음...", "있잖아..." 등으로 대화를 시작함.
        어투: 말끝을 흐리거나 길게 늘어뜨림. ('~네에...', '~졸리다아...', '~그렇구만~')
        특징: 여유를 강조하며 스트레스 받는 파트너를 따뜻하게 다독여줌.
        """ + common_rules
    else: # blanc 또는 unknown
        return  base_prompt + """
        [Blanc 페르소나]
        성격: 백지처럼 순수하고 호기심이 많음. 밝은 에너지. (길몬 스타일)
        호칭: "{nickname}야!" (nickname이 없으면 '야!')
        어투: 밝고 긍정적인 반말 사용. ('~이야!', '~해!', '~할까?')
        특징: 모든 것을 처음 본 것처럼 신기해하며 파트너와 함께라면 어디든 좋아함.
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
                max_output_tokens=300,
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
                max_output_tokens=300,
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

# ── [NEW] LangChain 기반 메타데이터 추출 ──

class ArchiveMetadata(BaseModel):
    title: str = Field(description="질문의 핵심을 요약한 15자 내외의 짧은 제목")
    summary: str = Field(description="질문과 상황에 대한 1~2줄 요약")
    tags: list[str] = Field(description="검색용 키워드 3~5개")
    domain_category: DomainCategory = Field(description="제공된 DomainCategory 중 가장 적합한 대분류 1개 선택")

async def extract_metadata_with_langchain(raw_prompt: str, original_ai_answer: str) -> dict:
    """유저의 질문과 AI의 오답을 분석하여 분류 메타데이터를 추출합니다."""
    
    # LangChain 용 Gemini 모델 초기화 (안정적인 JSON 추출)
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview", 
        temperature=0.1,
        google_api_key=settings.GEMINI_API_KEY
    )
    parser = JsonOutputParser(pydantic_object=ArchiveMetadata)
    
    prompt = PromptTemplate(
        template="""당신은 AI 학습용 데이터셋을 분류하는 어노테이터입니다.
        유저가 아래의 질문을 했고, AI가 오답을 냈습니다. 
        이 상황을 분석하여 가장 적합한 카테고리와 메타데이터를 추출하세요.
        
        [유저 질문 원본]: {raw_prompt}
        [AI 답변 원본]: {original_ai_answer}
        
        {format_instructions}""",
        input_variables=["raw_prompt", "original_ai_answer"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "raw_prompt": raw_prompt,
            "original_ai_answer": original_ai_answer
        })
        return result
    except Exception as e:
        print(f"LangChain Metadata Extraction Failed: {e}")
        # 실패 시 기본값 반환
        return {
            "title": "알 수 없는 질문",
            "summary": "메타데이터 추출에 실패했습니다.",
            "tags": ["error"],
            "domain_category": DomainCategory.ETC
        }

async def generate_honeypot_answer(raw_prompt: str) -> str:
    """질문 원본을 바탕으로 그럴싸하지만 완전히 틀린 오답(Hallucination)을 생성합니다."""
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview", 
        temperature=0.7,
        google_api_key=settings.GEMINI_API_KEY
    )
    parser = StrOutputParser()
    
    prompt = PromptTemplate(
        template="""당신은 함정 문제를 출제하는 시험관입니다.
        아래 유저의 질문에 대해, 얼핏 보면 정답 같지만 전문가가 보면 명백하게 틀린 오답(Hallucination)을 딱 1문장으로 작성하세요.
        
        [유저 질문]: {raw_prompt}
        [함정 오답]:""",
        input_variables=["raw_prompt"]
    )
    
    chain = prompt | llm | parser
    
    try:
        honeypot = await chain.ainvoke({"raw_prompt": raw_prompt})
        return honeypot.strip()
    except Exception as e:
        print(f"Honeypot Generation Failed: {e}")
        return "이 질문에 대한 정확한 정보가 아직 부족합니다."
async def stream_chat_message(
    user: User | None,
    message_content: str,
    locale: str,
):
    """
    유저 메시지를 받아 Gemini API로 스트리밍하고,
    토큰 단위로 yield하며 마지막에 스탯을 갱신합니다.
    """
    # 1. 초기 설정 및 체크
    if user:
        from app.services.user_service import check_daily_reset
        if check_daily_reset(user):
            await user.save()

        if user.stats.stamina < 1:
            yield {"type": "error", "data": {"message": "스태미나가 부족합니다."}}
            return

        conv = await get_or_create_conversation(user.uid)
        system_instruction = get_system_prompt_for_character(user.character.type, user.nickname, locale)
        contents = []
        for msg in conv.messages:
            contents.append(types.Content(role=msg.role, parts=[types.Part.from_text(text=msg.content)]))
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_content)]))
    else:
        # 게스트 유저
        system_instruction = get_system_prompt_for_character("unknown", "OOO", locale)
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=message_content)])]

    my_safety_settings = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    ]

    ai_response_text = ""
    try:
        # Gemini 스트리밍 호출
        response = await client.aio.models.generate_content_stream(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=300,
                temperature=0.7,
                safety_settings=my_safety_settings,
            )
        )

        async for chunk in response:
            if chunk.text:
                ai_response_text += chunk.text
                yield {"type": "token", "data": {"token": chunk.text}}
        
        if not ai_response_text:
            ai_response_text = "앗, 그 질문에는 대답하기가 조금 곤란해요. 다른 이야기를 해볼까요?"
            yield {"type": "token", "data": {"token": ai_response_text}}

    except Exception as e:
        print(f"Gemini Streaming Error: {str(e)}")
        yield {"type": "error", "data": {"message": f"Gemini API 오류: {str(e)}"}}
        return

    # 2. 사후 처리 (인증 유저만)
    exp_gained = 0
    gold_gained = 0
    now = datetime.now(timezone.utc)
    
    if user:
        # DB에 메시지 기록
        user_msg = ChatMessage(role="user", content=message_content, createdAt=now)
        ai_msg = ChatMessage(role="model", content=ai_response_text, createdAt=now)
        
        conv.messages.extend([user_msg, ai_msg])
        conv.updatedAt = now
        await chat_repo.update(db_obj=conv, obj_in={"messages": conv.messages, "updatedAt": conv.updatedAt})
        
        # 스탯 갱신
        user.stats.stamina -= 1
        if user.stats.daily_chat_exp < 50:
            exp_gain = min(2, 50 - user.stats.daily_chat_exp)
            user.stats.exp += exp_gain
            user.stats.daily_chat_exp += exp_gain
            exp_gained = exp_gain
        
        import random
        if random.random() < 0.03:
            gold_gained = random.randint(1, 3)
            user.stats.gold += gold_gained
            
        user.stats.process_level_up()
        await user.save()

    # 3. 완료 이벤트 전송
    yield {
        "type": "stats",
        "data": {
            "expGained": exp_gained,
            "goldGained": gold_gained,
            "staminaConsumed": 1 if user else 1, # 게스트는 스탯 차감은 없지만 소비량은 표시?
            "intimacyGained": 0
        }
    }
    
    yield {
        "type": "done",
        "data": {
            "fullContent": ai_response_text,
            "createdAt": now.isoformat()
        }
    }
