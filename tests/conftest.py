import os

os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test_super_secret_key"
os.environ["GEMINI_API_KEY"] = "test_gemini_key"
os.environ["MONGODB_URL"] = "mongodb://localhost:27017"

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from typing import AsyncGenerator
import fakeredis.aioredis
from unittest.mock import patch
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

# Ensure asyncio loop scope is properly handled
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

# Setup DB explicitly
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    client = AsyncMongoMockClient()
    database = client["test_db"]
    
    from app.models.user import User
    from app.models.chat import ChatConversation
    from app.models.archive import ArchivePost, ArchiveAnswer
    from app.models.academy import KnowledgeCard
    from app.models.mailbox import Mail

    await init_beanie(
        database=database,
        document_models=[User, ChatConversation, ArchivePost, ArchiveAnswer, KnowledgeCard, Mail],
    )
    yield database

# Patch main app lifespan logic
@pytest_asyncio.fixture(scope="session")
async def test_app(setup_db):
    from app.main import app
    from app.core import redis as redis_module
    
    # Mock redis client with fakeredis
    fake_redis = fakeredis.aioredis.FakeRedis()
    redis_module.redis_client = fake_redis
    
    # Patch lifespan of main app to not initialize real db
    with patch("app.main.init_db", return_value=None), patch("app.main.init_redis", return_value=None), patch("app.main.close_redis", return_value=None):
        async with LifespanManager(app):
            yield app

@pytest_asyncio.fixture(scope="session")
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        yield client
