from fastapi import HTTPException, status

class DomainError(Exception):
    """기본 도메인 커스텀 예외"""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code

class NotFoundError(DomainError):
    def __init__(self, resource_name: str):
        super().__init__(f"{resource_name}을(를) 찾을 수 없습니다.", status.HTTP_404_NOT_FOUND)

class InsufficientResourceError(DomainError):
    def __init__(self, resource_name: str):
        super().__init__(f"{resource_name}이(가) 부족합니다.", status.HTTP_400_BAD_REQUEST)

class InvalidRequestError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)
