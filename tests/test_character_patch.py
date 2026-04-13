import pytest
from httpx import AsyncClient
from app.models.user import User
from app.main import app
from app.core.security import get_current_user

pytestmark = pytest.mark.asyncio

async def test_patch_character_type(async_client: AsyncClient):
    # 1. Create a test user
    test_user = User(
        uid="patch_test_uid",
        nickname="PatchTester",
        email="patch@example.com"
    )
    await test_user.insert()

    # 2. Mock get_current_user to return our test user
    app.dependency_overrides[get_current_user] = lambda: test_user

    try:
        # 3. Call PATCH /api/v1/users/me/character/type
        patch_data = {"type": "new_type"}
        response = await async_client.patch("/api/v1/users/me/character/type", json=patch_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["character"]["type"] == "new_type"
        
        # 4. Verify in DB
        updated_user = await User.find_one(User.uid == "patch_test_uid")
        assert updated_user.character.type == "new_type"

        # 5. Verify security: email and password should NOT be in the response
        assert "email" not in data
        assert "password" not in data
        
        # 6. Double check get_my_profile also doesn't have sensitive data
        response = await async_client.get("/api/v1/users/me")
        assert response.status_code == 200
        data = response.json()
        assert "email" not in data
        assert "password" not in data
        assert data["character"]["type"] == "new_type"

    finally:
        # Clean up dependency override
        app.dependency_overrides.clear()
