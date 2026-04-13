import pytest
from httpx import AsyncClient
from app.models.user import User
from app.db.repository.user_repository import user_repo

pytestmark = pytest.mark.asyncio

async def test_user_creation_and_profile(async_client: AsyncClient):
    # Setup test user directly through repo
    new_user = User(
        uid="test_uid_123",
        nickname="TestUser",
        email="test@example.com"
    )
    await user_repo.create(obj_in=new_user)
    
    # Check if we can get it from the endpoint
    response = await async_client.get("/api/v1/users/test_uid_123")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "test_uid_123"
    assert data["nickname"] == "TestUser"
