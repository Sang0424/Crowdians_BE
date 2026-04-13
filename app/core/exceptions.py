from fastapi import HTTPException, status

class DomainError(Exception):
    """기본 도메인 커스텀 예외 (국제화 대응을 위한 code 필드 포함)"""
    def __init__(
        self, 
        message: str, 
        status_code: int = status.HTTP_400_BAD_REQUEST, 
        code: str = "INTERNAL_ERROR",
        params: dict = None
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.params = params or {}

class NotFoundError(DomainError):
    def __init__(self, resource_name: str):
        super().__init__(f"{resource_name}을(를) 찾을 수 없습니다.", status.HTTP_404_NOT_FOUND, "NOT_FOUND")

class InsufficientResourceError(DomainError):
    def __init__(self, resource_name: str):
        super().__init__(f"{resource_name}이(가) 부족합니다.", status.HTTP_400_BAD_REQUEST, "INSUFFICIENT_RESOURCE")

class InvalidRequestError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, "INVALID_REQUEST")

# ── Gemini API 관련 예외 (I18n 대응) ──

class GeminiAPIError(DomainError):
    """Gemini API 관련 기본 예외"""
    pass

class GeminiRateLimitError(GeminiAPIError):
    """429 - RESOURCE_EXHAUSTED"""
    def __init__(self):
        super().__init__(
            "현재 요청이 너무 많아 잠시 후 다시 시도해주시기 바랍니다.", 
            status.HTTP_429_TOO_MANY_REQUESTS, 
            "GEMINI_RATE_LIMIT"
        )

class GeminiSafetyBlockError(GeminiAPIError):
    """안전 필터에 의해 응답이 차단됨"""
    def __init__(self):
        super().__init__(
            "부적절한 내용이 포함되어 응답할 수 없습니다. 다른 질문을 해주세요.", 
            status.HTTP_400_BAD_REQUEST, 
            "GEMINI_SAFETY_BLOCK"
        )

class GeminiAuthError(GeminiAPIError):
    """401/403 - API KEY 오류"""
    def __init__(self):
        super().__init__(
            "AI 서비스 인증에 실패했습니다. 관리자에게 문의하세요.", 
            status.HTTP_503_SERVICE_UNAVAILABLE, 
            "GEMINI_AUTH_ERROR"
        )

class GeminiServerError(GeminiAPIError):
    """5xx - Gemini 서버 장애"""
    def __init__(self, message: str = "AI 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요."):
        super().__init__(
            message, 
            status.HTTP_502_BAD_GATEWAY, 
            "GEMINI_SERVER_ERROR"
        )

class GeminiInvalidRequestError(GeminiAPIError):
    """400 - 잘못된 요청 (프롬프트 오류 등)"""
    def __init__(self, detail: str = ""):
        super().__init__(
            f"AI 요청 처리 중 문제가 발생했습니다.{f' ({detail})' if detail else ''}", 
            status.HTTP_400_BAD_REQUEST, 
            "GEMINI_INVALID_REQUEST"
        )
