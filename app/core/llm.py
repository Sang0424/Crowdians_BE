# app/core/llm.py

import json
from google import genai
from app.core.config import settings

async def generate_tags_and_summary(content: str) -> dict:
    """긴 본문을 3줄 요약하고 핵심 태그를 추출합니다."""
    
    # ── Gemini Client ──
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = f"""
    Please analyze the following content and:
    1. Summarize it in exactly 3 bullet points in Korean.
    2. Extract 2-5 relevant tags in Korean.
    
    Response MUST be in JSON format:
    {{
        "summary": "1. 첫번째 요약\\n2. 두번째 요약\\n3. 세번째 요약",
        "tags": ["태그1", "태그2"]
    }}
    
    Content:
    {content}
    """
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            }
        )
        
        # JSON 파싱
        # response.text is the JSON string
        return json.loads(response.text)
    except Exception as e:
        print(f"LLM Error: {e}")
        return {
            "summary": "요약을 생성하는 중 오류가 발생했습니다.",
            "tags": []
        }
