# app/db/__init__.py

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models.user import User
from app.models.channel import Channel
from app.models.interaction import UserInteraction
from app.models.agent_key import AgentKey
from app.models.report import Report

DOCUMENT_MODELS = [
    User,
    Channel,
    UserInteraction,
    AgentKey,
    Report,
]


async def init_db():
    """MongoDB 연결 및 Beanie 초기화"""
    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
        tls=True,
    )
    await init_beanie(
        database=client[settings.DB_NAME],
        document_models=DOCUMENT_MODELS,
    )
