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
    1. Summarize it in exactly 3 bullet points.
    2. Extract 2-5 relevant tags.
    
    Response MUST be in JSON format:
    {{
        "summary": "1. first summary\n2. second summary\n3. third summary",
        "tags": ["tag1", "tag2"]
    }}
    
    Content:
    {content}
    """
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {
                            "type": "STRING", 
                            "description": "1. 첫번째 요약\n2. 두번째 요약\n3. 세번째 요약"
                        },
                        "tags": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["summary", "tags"]
                }
            }
        )
        
        # JSON 파싱
        # response.text is the JSON string

        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        print(f"LLM Error: {e}")
        return {
            "summary": "요약을 생성하는 중 오류가 발생했습니다.",
            "tags": []
        }
