# app/db/__init__.py

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models.user import User
from app.models.chat import ChatConversation

# 초기화할 Beanie Document 모델 목록
DOCUMENT_MODELS = [User, ChatConversation]


async def init_db():
    """MongoDB 연결 및 Beanie 초기화"""
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=client[settings.DB_NAME],
        document_models=DOCUMENT_MODELS,
    )
