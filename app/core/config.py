# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── MongoDB ──
    MONGODB_URL: str
    DB_NAME: str

    # ── JWT ──
    JWT_SECRET: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # ── Firebase ──
    GOOGLE_APPLICATION_CREDENTIALS: str
    GEMINI_API_KEY: str

    # ── Redis ──
    REDIS_URL: str

    # ── Internal API (NextAuth ↔ Backend 서버 간 인증) ──
    INTERNAL_API_KEY: str

    # ── Donation ──
    KOFI_VERIFICATION_TOKEN: str = ""
    CRYPTO_WALLET_ADDRESS: str = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e" # Placeholder

    # ── CORS ──
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    model_config = SettingsConfigDict(env_file=".env.local", extra="allow")


settings = Settings()