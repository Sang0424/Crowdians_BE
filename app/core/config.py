import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Environment ──
    APP_ENV: str = "dev"

    # ── MongoDB ──
    MONGODB_URL: str
    DB_NAME: str

    # ── JWT ──
    JWT_SECRET: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # ── Firebase & AI ──
    GOOGLE_APPLICATION_CREDENTIALS: str
    GEMINI_API_KEY: str

    # ── Redis ──
    REDIS_URL: str

    # ── Internal API (NextAuth ↔ Backend 서버 간 인증) ──
    INTERNAL_API_KEY: str

    # ── Lemon Squeezy (Subscription) ──
    LEMONSQUEEZY_API_KEY: str = ""
    LEMONSQUEEZY_WEBHOOK_SECRET: str = ""
    LEMONSQUEEZY_VARIANT_ID: str = ""
    LEMONSQUEEZY_STORE_ID: str = ""
    LEMONSQUEEZY_STORE_SUBDOMAIN: str = "crowdians"  # Lemon Squeezy store subdomain
    FRONTEND_URL: str = "http://localhost:3000"

    # ── CORS ──
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


def get_settings():
    app_env = os.getenv("APP_ENV", "dev")
    env_file = f".env.{app_env}"
    
    # Check if env file exists, otherwise fallback to .env or .env.local
    if not os.path.exists(env_file):
        if os.path.exists(".env"):
            env_file = ".env"
        elif os.path.exists(".env.local"):
            env_file = ".env.local"
            
    return Settings(_env_file=env_file)


settings = get_settings()