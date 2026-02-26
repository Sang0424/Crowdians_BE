# app/core/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── MongoDB ──
    MONGODB_URL: str = "mongodb://localhost:27017"
    DB_NAME: str = "crowdians_db"

    # ── JWT ──
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24시간

    # ── Firebase ──
    # 환경변수 GOOGLE_APPLICATION_CREDENTIALS 로 서비스 계정 키 경로를 지정
    # 예: export GOOGLE_APPLICATION_CREDENTIALS="/path/to/firebase-service-account.json"

    # ── CORS ──
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    class Config:
        env_file = ".env"


settings = Settings()