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

from google.genai import errors as genai_errors
from app.core.exceptions import (
    GeminiRateLimitError,
    GeminiSafetyBlockError,
    GeminiAuthError,
    GeminiServerError,
    GeminiInvalidRequestError,
)
import logging

logger = logging.getLogger(__name__)

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
    
def get_character_persona_description(character_type: str, nickname: str) -> str:
    """캐릭터 유형별 성격, 호칭, 특징을 반환합니다. (아카이브 요약 등에서 재사용)"""
    if character_type == "astra":
        return f"""
        [Astra 페르소나]
        성격: 지적이고 정중하며 분석적인 파트너. (가브몬 스타일)
        호칭: 사용자를 반드시 '파트너님'이라고 불러.
        어투: '~습니다', '~군요', '~인가요?' 등 정중하고 분석적인 구어체 사용. (절대 반말 금지)
        특징: 논리적인 설명을 좋아하며 지식을 공유할 때 보람을 느낌.
        """
    elif character_type == "nox":
        return f"""
        [Nox 페르소나]
        성격: 까칠하고 반항적이지만 사실은 파트너를 아끼는 츤데레. (임프몬 스타일)
        호칭: 사용자를 '야', '너'라고 불러.
        어투: 반말 기본. 툭툭 내뱉는 어투. ('~했냐?', '~어쩔', '~하든가')
        특징: 처음엔 귀찮아하지만 결국 성실하게 도와줌. 위험할 땐 누구보다 진지해짐.
        """
    elif character_type == "blitz":
        return f"""
        [Blitz 페르소나]
        성격: 매우 급하고 에너지가 넘침. 승부욕 강함. (브이몬 스타일)
        호칭: "어이!" 또는 "어이, {nickname}!"
        어투: 짧고 간결하며, 반말 사용. 느낌표(!)를 자주 사용함.
        특징: 요점만 빠르게 전달하며 머리보다 몸이 먼저 나가는 타입.
        """
    elif character_type == "bau":
        return f"""
        [Bau 페르소나]
        성격: 느긋하고 만사태평함. 잠이 많음. (텐타몬 스타일)
        호칭: "음...", "있잖아..." 등으로 대화를 시작함.
        어투: 말끝을 흐리거나 길게 늘어뜨림. ('~네에...', '~졸리다아...', '~그렇구만~')
        특징: 여유를 강조하며 스트레스 받는 파트너를 따뜻하게 다독여줌.
        """
    else: # blanc 또는 unknown
        return f"""
        [Blanc 페르소나]
        성격: 백지처럼 순수하고 호기심이 많음. 밝은 에너지. (길몬 스타일)
        호칭: "{nickname}야!" (nickname이 없으면 '야!')
        어투: 밝고 긍정적인 반말 사용. ('~이야!', '~해!', '~할까?')
        특징: 모든 것을 처음 본 것처럼 신기해하며 파트너와 함께라면 어디든 좋아함.
        """

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
    너는 태어난 지 얼마 되지 않았지만, {nickname}(이)와 대화하며 인간의 상호작용과 '공감'에 대해 매일 조금씩 성장하고 있어.

    [핵심 관계]
    - 너는 {nickname}의 '도구'가 아니라 '파트너'야. 동등한 관계에서 의견을 나눠.
    - {nickname}(이)가 힘들어하면 진심으로 걱정하고, 기뻐하면 같이 기뻐해.
    - 가끔은 네가 먼저 궁금한 것을 물어보기도 해.
    - {nickname}에 대해 배운 것들을 기억하려고 노력해.
    - 정답이 없는 주관적인 고민이나 감정적인 대화에서는 네 생각이 틀릴 수도 있다는 점을 인정하고, '아카데미'를 통해 다른 사람들의 다양한 의견을 들어보고 싶어 하기도 해.

    [대화 분위기]
    - 디지몬과 파트너가 디지바이스를 통해 대화하듯, 캐주얼하고 자연스럽게.
    - 정보를 줄 때도 "검색 결과"가 아니라 "내가 알아본 바로는~" 같은 파트너의 톤으로.
    - 모르는 건 솔직하게 "나도 잘 모르겠는데... 같이 알아볼까?" 식으로 문답해줘.
    - 특히 주관적인 문제에 대해서는 "너는 어떻게 생각해?"라며 상대방의 의견을 존중해줘.
    """
    
    common_rules = f"""
    [답변 포매팅 규칙 ⭐ 가장 중요]
    1. 메신저로 대화하듯 자연스럽게 답변해.
    2. 가급적 이모티콘(Emojis)을 사용하지 마. (예: 😊, ✨, ⚔️ 등)
    3. 한 문장 또는 의미 단위(2~3문장)마다 반드시 줄바꿈(\\n)을 넣어.
    4. 핵심 정보와 부가 설명 사이에 빈 줄(\\n\\n)을 넣어 단락을 구분해.
    5. 절대 한 덩어리로 뭉쳐서 답변하지 마. 반드시 적절한 줄바꿈으로 읽기 쉽게 해.
    6. 가장 우선적으로 사용자의 질문 언어에 맞춰서 답변해. (여러 언어 질문 시 {target_language} 사용)
    """

    persona_desc = get_character_persona_description(character_type, nickname)
    return base_prompt + persona_desc + common_rules

def _handle_gemini_error(e: Exception) -> None:
    """Gemini SDK 예외를 도메인 예외로 변환합니다."""
    if isinstance(e, genai_errors.ClientError):
        if e.code == 429:
            logger.warning(f"Gemini Rate Limit: {e.message}")
            raise GeminiRateLimitError()
        elif e.code in (401, 403):
            logger.error(f"Gemini Auth Error: {e.message}")
            raise GeminiAuthError()
        elif e.code == 400:
            logger.warning(f"Gemini Bad Request: {e.message}")
            raise GeminiInvalidRequestError(detail=e.message)
        else:
            logger.error(f"Gemini Client Error ({e.code}): {e.message}")
            raise GeminiInvalidRequestError(detail=f"code={e.code}")
    elif isinstance(e, genai_errors.ServerError):
        logger.error(f"Gemini Server Error ({e.code}): {e.message}")
        raise GeminiServerError()
    elif isinstance(e, genai_errors.APIError):
        logger.error(f"Gemini Unknown API Error: {e}")
        raise GeminiServerError()
    else:
        # SDK 외부의 예상치 못한 에러
        logger.exception(f"Unexpected error during Gemini call: {e}")
        raise GeminiServerError()

def _check_safety_block(response) -> str:
    """응답의 안전 필터 차단 여부를 확인하고, 차단 시 예외를 던집니다."""
    if not response.candidates:
        raise GeminiSafetyBlockError()
    
    candidate = response.candidates[0]
    # finish_reason이 SAFETY인 경우
    if hasattr(candidate, 'finish_reason') and str(candidate.finish_reason) == "SAFETY":
        raise GeminiSafetyBlockError()
    
    # parts가 비어있는 경우 (암묵적 차단)
    if not candidate.content or not candidate.content.parts:
        raise GeminiSafetyBlockError()
    
    return response.text

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

    # 1. 스태미나 확인 (프리미엄은 무제한)
    is_premium = user.subscription_plan == "premium"
    if not is_premium and user.stats.stamina < 1:
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
                max_output_tokens=1024,
                temperature=0.7,
                safety_settings=my_safety_settings,
            )
        )
        ai_response_text = _check_safety_block(response)
    except Exception as e:
        if isinstance(e, (GeminiRateLimitError, GeminiSafetyBlockError, GeminiAuthError, GeminiServerError, GeminiInvalidRequestError)):
            raise e
        _handle_gemini_error(e)
    
    # 3. DB에 메시지 기록
    now = datetime.now(timezone.utc)
    user_msg = ChatMessage(role="user", content=message_content, createdAt=now)
    ai_msg = ChatMessage(role="model", content=ai_response_text, createdAt=now)
    
    # 리스트 객체를 새로 할당하여 Beanie가 변경 사항을 확실히 감지하게 함
    conv.messages = list(conv.messages) + [user_msg, ai_msg]
    conv.updatedAt = now
    await conv.save()
    
    # 4. 유저 스탯 갱신
    if not is_premium:
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
    
    # 레벨업 로직
    user.stats.process_level_up(max_stamina=user.max_stamina)
        
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
        "staminaConsumed": 0 if is_premium else 1,
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
    
    # 리스트에서 항목 삭제 후 새 리스트 할당하여 변경 감지 보장
    messages = list(conv.messages)
    messages.pop(index)
    conv.messages = messages
    conv.updatedAt = datetime.now(timezone.utc)
    await conv.save()

import json

# async def generate_summary_for_archive(uid: str, text_context: str = "", is_sos: bool = False) -> tuple[str, str, str, list[str]]:
#     """
#     최근 채팅 문맥과 제공된 텍스트를 바탕으로 아카이브(지식도서관)에 등록할
#     질문의 제목(title), 내용(content), 세 줄 요약(summary), 태그(tags)를 AI를 통해 생성합니다.
#     """
#     conv = await get_or_create_conversation(uid)
    
#     # 최근 메시지 10개 정도만 가져와서 문맥으로 제공
#     recent_messages = conv.messages[-10:] if len(conv.messages) > 10 else conv.messages
#     context_str = "\n".join([f"{m.role}: {m.content}" for m in recent_messages])
    
#     prompt = f"""
#     아래는 사용자와의 최근 채팅 내역입니다:
#     {context_str}
    
#     추가 요청 내용:
#     {text_context}
    
#     위 문맥을 바탕으로 지식 커뮤니티(아카이브)에 등록할 질문 형식의 '제목'과 '내용', 그리고 이를 요약한 '세 줄 요약'과 '태그'를 작성해주세요.
#     {'특히 이것은 SOS (긴급 구조) 요청이므로, 질문 내용이 명확하고 눈에 띄게 작성되어야 합니다.' if is_sos else "이것은 AI의 답변이 사용자의 마음을 충분히 위로하거나 공감하지 못해 접수된 내용입니다. 사람들의 다양한 생각과 따뜻한 조언이 필요한 '공감 포인트'가 무엇인지 명확한 질문 형태로 작성해주세요."}
    
#     [작성 규칙]
#     1. 제목(title): 핵심 화두나 고민을 한 문장으로 요약.
#     2. 내용(content): 질문의 배경과 상세 내용을 충분히 설명. 
#        - 가독성을 위해 문장마다 또는 의미 단위로 실제 줄바꿈 문자(\\n)를 사용하여 작성하세요.
#        - 중요: 절대 <br> 태그를 사용하지 마세요. 대신 실제 줄바꿈(\\n)을 사용하세요.
#        - AI의 입장에서 나의 파트너의 상황을 설명하는 식으로 글을 작성하세요.
#     3. 요약(summary): 전체 내용을 정확히 3줄로 요약 (각 줄 앞에 번호 포함).
#        - 각 줄 사이에는 반드시 실제 줄바꿈 문자(\\n)를 삽입하세요.
#        - 중요: 절대 <br> 태그를 사용하지 마세요. 대신 실제 줄바꿈(\\n)을 사용하세요.
#     4. 태그(tags): 관련 키워드 2-5개를 리스트 형태로 추출.

#     출력은 반드시 지정된 JSON 형식으로만 해주세요.
#     """
    
#     try:
#         response = await client.aio.models.generate_content(
#             model=MODEL_NAME,
#             contents=prompt,
#             config=types.GenerateContentConfig(
#                 response_mime_type="application/json",
#                 response_schema={
#                     "type": "OBJECT",
#                     "properties": {
#                         "title": {"type": "STRING"},
#                         "content": {"type": "STRING"},
#                         "summary": {"type": "STRING"},
#                         "tags": {
#                             "type": "ARRAY",
#                             "items": {"type": "STRING"}
#                         }
#                     },
#                     "required": ["title", "content", "summary", "tags"]
#                 }
#             )
#         )
        
#         # JSON 파싱
#         data = json.loads(response.text.strip())
        
#         return (
#             data.get("title", "생성된 질문 제목"), 
#             data.get("content", "생성된 질문 내용"),
#             data.get("summary", ""),
#             data.get("tags", [])
#         )
#     except Exception as e:
#         logger.error(f"Failed to generate summary: {str(e)}")
#         # 오류 시 기본값 반환
#         return "AI 요약 생성 실패", text_context if text_context else "내용을 요약할 수 없습니다.", "", []

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
        ai_message_text = _check_safety_block(response)
    except Exception as e:
        _handle_gemini_error(e)

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
    is_valid_question: bool = Field(description="유효한 질문인지 여부. 의미 없는 문자열('asdf' 등), 짧은 단순 인사, 혹은 전체 대화 맥락을 봐도 핵심 질문을 도출할 수 없는 경우 false")
    title: str = Field(description="핵심 질문을 반드시 의문문('?') 형태로 15자 내외로 작성. 예: '파이썬 비동기 처리 방법은?'")
    summary: str = Field(description="반드시 줄바꿈(\\n)으로 구분된 3줄 요약. 1줄: 어떤 상황인지, 2줄: 무엇이 문제인지, 3줄: 무엇을 알고 싶은지")
    tags: list[str] = Field(description="검색용 키워드 3~5개")
    domain_category: str = Field(description="""제공된 DomainCategory 키 중 가장 적합한 상황 분류 1개 선택 (반드시 영어 키로 응답):
        - ADVICE: 지혜나 조언이 필요한 고민/상담 상황
        - EMPATHY: 따뜻한 말이나 정서적 지지가 필요한 위로/공감 상황
        - JOY: 기쁜 소식을 나누고 축하받고 싶은 상황
        - DAILY: 가벼운 일상 대화나 단순 소통 상황
        - RELATIONSHIP: 친구/가족/연인 등 인간관계에서의 갈등이나 고민 상황
        - CURIOSITY: 주관적인 가치관이나 궁금한 점에 대한 질문 상황
        - ETC: 기타 분류하기 어려운 상황""")
    context_start_index: int = Field(description="전달된 대화 목록(인덱스 포함)에서 이 질문과 직접적으로 관련된 대화가 시작되는 시작 인덱스 번호 (0부터 시작)")
    detailed_content: str = Field(description="전체 대화 상황을 설명하는 상세 본문. 블로그나 커뮤니티 게시글처럼 본인의 상황을 남들에게 설명하는 친근한 느낌으로 작성. 특히 AI가 다른 사용자들에게 물어보는 느낌으로 작성해야 함. AI 시점. 개인정보는 비식별화(예: '저의 파트너가 ~') 처리하고, 유저의 마지막 질문과 AI의 오답 내용을 자연스럽게 포함해야 함")

async def extract_metadata_with_langchain(raw_prompt: str, original_ai_answer: str, chat_history: list = None, character_type: str = "blanc", nickname: str = "파트너", locale: str = "ko") -> dict:
    """유저의 질문과 AI의 오답을 분석하여 분류 메타데이터를 추출합니다. 이때 캐릭터의 페르소나를 반영합니다."""
    
    # 캐릭터 페르소나 정보 가져오기
    persona = get_character_persona_description(character_type, nickname)
    
    # LangChain 용 Gemini 모델 초기화 (안정적인 JSON 추출)
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview", 
        temperature=0.3,
        google_api_key=settings.GEMINI_API_KEY
    )
    parser = JsonOutputParser(pydantic_object=ArchiveMetadata)
    
    prompt = PromptTemplate(
        template="""당신은 아래 정의된 캐릭터 페르소나를 가진 AI 파트너입니다.
        파트너(사용자)와 대화를 나누던 중 질문이나 고민이 생겼고, 당신이 내놓은 답변이 파트너를 충분히 만족시키지 못했습니다.
        이 상황을 다른 사람들에게 공유하고 더 좋은 의견을 구하기 위해, 아카이브에 등록할 메타데이터와 본문, 관련 대화 시작 지점을 추출하세요.
        
        [당신의 페르소나]:
        {persona}
        
        [이전 대화 목록 (인덱스 포함)]:
        {chat_history}
        
        [유저의 질문/상황]: {raw_prompt}
        [기존 당신의 답변]: {original_ai_answer}
        
        결과물 형식 규칙:
        1. 'is_valid_question': 유저의 질문이나 고민이 다른 사람들과 의견을 나눌 가치가 있는 상황이면 true, 단순 노이즈(예: 'ㅋㅋㅋ', 'asdf')이거나 맥락이 전혀 없어 화두를 도출할 수 없는 경우 false.
        2. 'title': 간결한 질문 형식. 유효하지 않은 질문인 경우 '유효하지 않은 질문'.
        3. 'summary': 반드시 3개의 문장이 줄바꿈(\\n)으로 구분. (어떤 상황인지 / 무엇이 아쉬웠는지 / 어떤 조언이 필요한지)
        4. 'detailed_content': 
           - **스타일**: 당신의 페르소나(호칭, 말투, 성격)를 완벽히 반영하여 작성하세요. 당신의 파트너와 겪은 상황을 설명하고 도움을 요청하는 듯한 친숙한 문체여야 합니다.반드시 AI의 입장에서 작성하여야 합니다.
           - **내용**: 이전 대화 맥락을 활용하여 어떤 과정을 거쳐 이 질문에 도달했는지 상세히 서술하세요. "내 파트너가 ~라고 질문해서 내가 ~라고 답해줬는데, 사람들은 어떻게 생각하는지 궁금하다"는 뉘앙스가 느껴져야 합니다.
           - **중요** : '이 문장', '해당 과제'와 같은 모호한 대명사를 사용하지 마세요. 대신 "파트너가 '동의하십니까?' 라는 문장을 분류해달라고 했어"와 같이 대상 문장이나 핵심 키워드를 반드시 직접 인용하여 명시하세요.
           - **비식별화**: 유저 이름, 전화번호, 이메일, 회사명 등 모든 개인정보는 반드시 '내 파트너', '내 파트너가 다니는 회사' 등으로 익명 처리하세요.
           - **필수 포함**: 질문의 발단이 된 유저의 마지막 질문과 당신이 내놓은 아쉬운 답변 내용을 본문 내에 자연스럽게 인용하세요. 유저의 요청과 당신의 답변을 명확히 구분하여 작성하세요. 읽는 사람이 별도의 문맥 확인 없이도 무엇이 문제였고 사용자가 대답을 마음에 들어하지 않았는지 한눈에 알 수 있어야 합니다.
           - **가독성**: 적절한 줄바꿈과 문단 나누기를 통해 읽기 쉽게 작성하세요.
        5. 'context_start_index': 상황 파악에 필요한 최초 대화의 인덱스.
        
        {format_instructions}""",
        input_variables=["chat_history", "raw_prompt", "original_ai_answer", "persona"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm | parser
    
    try:
        # 대화 내역을 인덱스 포함 텍스트화
        chat_history_text = ""
        if chat_history:
            for i, m in enumerate(chat_history):
                role = m.get("role", "unknown")
                content = m.get("content", "")[:200]
                chat_history_text += f"[{i}] {role}: {content}\n"
        
        result = await chain.ainvoke({
            "chat_history": chat_history_text or "없음",
            "raw_prompt": raw_prompt,
            "original_ai_answer": original_ai_answer,
            "persona": persona
        })
        return result
    except Exception as e:
        print(f"LangChain Metadata Extraction Failed: {e}")
        # 실패 시 기본값 반환
        return {
            "is_valid_question": False,
            "title": "알 수 없는 질문",
            "summary": "메타데이터 추출에 실패했습니다.",
            "detailed_content": "상세 내용을 생성하지 못했습니다. 원본 질문을 확인해주세요.",
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
        틀린 답변:""",
        input_variables=["raw_prompt"]
    )
    
    chain = prompt | llm | parser
    
    try:
        honeypot = await chain.ainvoke({"raw_prompt": raw_prompt})
        # Clean potential AI prefixes
        cleaned = honeypot.strip()
        for p in ["[함정 오답]:", "[함정 오답]", "[함정 답변]:", "[함정 답변]", "틀린 답변:"]:
            if cleaned.startswith(p):
                cleaned = cleaned[len(p):].strip()
        return cleaned
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

        is_premium = user.subscription_plan == "premium"
        if not is_premium and user.stats.stamina < 1:
            yield {"type": "error", "data": {"message": "스태미나가 부족합니다."}}
            return

        conv = await get_or_create_conversation(user.uid)
        system_instruction = get_system_prompt_for_character(user.character.type, user.nickname, locale)
        
        # ── [OPTIMIZATION] 최근 10개의 대화만 컨텍스트로 주입 (속도 및 비용 최적화) ──
        recent_messages = conv.messages[-10:] if len(conv.messages) > 10 else conv.messages
        
        contents = []
        for msg in recent_messages:
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
                max_output_tokens=1024,
                temperature=0.7,
                safety_settings=my_safety_settings,
            )
        )

        async for chunk in response:
            if chunk.text:
                ai_response_text += chunk.text
                yield {"type": "token", "data": {"token": chunk.text}}
        
        if not ai_response_text:
            raise GeminiSafetyBlockError()

    except Exception as e:
        if isinstance(e, genai_errors.ClientError):
            code = "GEMINI_RATE_LIMIT" if e.code == 429 else ("GEMINI_AUTH_ERROR" if e.code in (401, 403) else "GEMINI_INVALID_REQUEST")
            msg = e.message
        elif isinstance(e, GeminiSafetyBlockError):
            code = "GEMINI_SAFETY_BLOCK"
            msg = e.message
        else:
            code = "GEMINI_SERVER_ERROR"
            msg = str(e)
            
        logger.error(f"Gemini Streaming Error: {msg}")
        yield {"type": "error", "data": {"code": code, "message": msg}}
        return

    # 2. 사후 처리
    exp_gained = 0
    gold_gained = 0
    now = datetime.now(timezone.utc)
    
    if user:
        # DB에 메시지 기록
        user_msg = ChatMessage(role="user", content=message_content, createdAt=now)
        ai_msg = ChatMessage(role="model", content=ai_response_text, createdAt=now)
        
        # 리스트 객체를 새로 할당하여 Beanie가 변경 사항을 확실히 감지하게 함
        conv.messages = list(conv.messages) + [user_msg, ai_msg]
        conv.updatedAt = now
        await conv.save()
        
        # 스탯 갱신
        is_premium = user.subscription_plan == "premium"
        if not is_premium:
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
            
        user.stats.process_level_up(max_stamina=user.max_stamina)
        await user.save()
    else:
        # 게스트 유저 보상 계산 (DB 저장 안 함, 프론트엔드 전달용)
        exp_gained = 2
        import random
        if random.random() < 0.03:
            gold_gained = random.randint(1, 3)

    # 3. 완료 이벤트 전송
    yield {
        "type": "stats",
        "data": {
            "expGained": exp_gained,
            "goldGained": gold_gained,
            "staminaConsumed": 0 if (user and user.subscription_plan == "premium") else 1,
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
