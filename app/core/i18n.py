# app/core/i18n.py

from typing import Any

# ── [TRANSLATIONS] 중앙 집중식 번역 데이터 ──
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ko": {
        "archive.rejection.title": "📚 지식 도서관 등록 보류 안내",
        "archive.rejection.content": (
            "안녕하세요, {nickname} 크라우디언님.\n\n"
            "제출해주신 Unlike/SOS 내역을 분석한 결과, 질문이 불분명하거나 대화 맥락이 부족하여 지식 도서관 및 아카데미에 등록되지 않았습니다.\n\n"
            "💡 거절 사유: {reason}\n\n"
            "정확한 지식 베이스 구축을 위해 더 구체적인 질문과 함께 다시 한 번 피드백을 남겨주시면 감사하겠습니다!"
        ),
        "chat.unlike.success": "답변이 신고되었습니다. 더 똑똑한 AI로 학습시키겠습니다.",
        "chat.sos.success": "지식 의뢰가 성공적으로 등록 되었습니다.",
        "common.error.unknown": "알 수 없는 오류가 발생했습니다.",
        "archive.default.reason": "질문의 핵심 내용을 파악할 수 없습니다.",
        "archive.commission.title": "🎯 새로운 직접 의뢰가 도착했습니다!",
        "archive.commission.content": "'{nickname}' 크라우디언님이 당신에게 직접 지식 의뢰를 보냈습니다.\n\n제목: {title}",
        "error.subscription.checkout_failed": "결제 세션을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.",
        "error.subscription.not_found": "구독 정보를 찾을 수 없습니다.",
        "error.limit_exceeded.sos": "오늘의 SOS 요청 횟수를 모두 사용하셨습니다. (일일 3회)",
        "error.limit_exceeded.commission": "오늘의 직접 의뢰 횟수를 모두 사용하셨습니다. (일일 1회)",
        "error.auth.unauthorized": "인증에 실패했습니다. 다시 로그인해주세요."
    },
    "en": {
        "archive.rejection.title": "📚 Archive Registration Postponed",
        "archive.rejection.content": (
            "Hello, Crowdians {nickname}.\n\n"
            "After analyzing your Unlike/SOS submission, it was not registered in the Knowledge Library and Academy due to unclear questions or lack of conversation context.\n\n"
            "💡 Reason for Rejection: {reason}\n\n"
            "We would appreciate it if you could leave feedback again with more specific questions to help build an accurate knowledge base!"
        ),
        "chat.unlike.success": "The response has been reported. We will use it to train a smarter AI.",
        "chat.sos.success": "The knowledge request (SOS) has been successfully registered.",
        "common.error.unknown": "An unknown error has occurred.",
        "archive.default.reason": "Cannot identify the core content of the question.",
        "archive.commission.title": "🎯 A new direct commission has arrived!",
        "archive.commission.content": "Crowdians '{nickname}' has sent you a direct knowledge request.\n\nTitle: {title}",
        "error.subscription.checkout_failed": "Failed to create checkout session. Please try again later.",
        "error.subscription.not_found": "Subscription information not found.",
        "error.limit_exceeded.sos": "You have reached your daily SOS request limit. (3 per day)",
        "error.limit_exceeded.commission": "You have reached your daily commission limit. (1 per day)",
        "error.auth.unauthorized": "Authentication failed. Please login again."
    },
    "ja": {
        "archive.rejection.title": "📚 知識図書館への登録保留のご案内",
        "archive.rejection.content": (
            "こんにちは、{nickname}様。\n\n"
            "提出いただいたUnlike/SOSの内容を分析した結果、質問が不明確であるか、会話の文脈이 부족하여 知識図書館およびアカデミーへの登録は見送られました。\n\n"
            "💡 保留理由: {reason}\n\n"
            "正確な知識ベース構築のため、より具体的な質問とともに、再度フィードバック을いただければ幸いです！"
        ),
        "chat.unlike.success": "回答が報告されました. よりスマートなAI의 학습에 활용させていただきます。",
        "chat.sos.success": "知識依頼 (SOS) 가 正常에 登録되었습니다.",
        "common.error.unknown": "不明なエラーが発生しました。",
        "archive.default.reason": "質問의 核心內容을 把握할 수 없습니다.",
        "archive.commission.title": "🎯 新しい直接依頼이 도착했습니다!",
        "archive.commission.content": "'{nickname}'様이 당신에게 직접 지식 의뢰를 보냈습니다.\n\n제목: {title}",
        "error.subscription.checkout_failed": "決済セッションの作成に失敗しました。後でもう一度お試しください。",
        "error.subscription.not_found": "購読情報が見つかりません。",
        "error.limit_exceeded.sos": "本日のSOS依頼制限に達しました。(1日3回)",
        "error.limit_exceeded.commission": "本日の直接依頼制限에 達했습니다. (1일 1회)",
        "error.auth.unauthorized": "認証に失敗しました。もう一度ログインしてください。"
    }
}

def get_text(key: str, locale: str = "ko", **kwargs: Any) -> str:
    """
    지정된 키와 로케일에 해당하는 번역 텍스트를 반환합니다.
    변수 치환({variable}) 기능이 포함되어 있습니다.
    """
    # 지원하지 않는 로케일일 경우 기본값 'ko' 사용
    lang_content = TRANSLATIONS.get(locale, TRANSLATIONS["ko"])
    
    # 해당 키가 없는 경우 그대로 키값을 반환하거나 ko의 것을 시도
    text = lang_content.get(key)
    if not text:
        text = TRANSLATIONS["ko"].get(key, key)
    
    # 변수 치환 처리
    try:
        return text.format(**kwargs)
    except KeyError as e:
        print(f"I18N Translation formatting error for key '{key}': {e}")
        return text
