import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

from unittest.mock import patch
from app.models.user import User
from app.db.repository.user_repository import user_repo
from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio


async def test_user_creation_and_profile(async_client: AsyncClient):
    # Setup test user directly through repo
    new_user = User(
        uid="test_uid_123",
        nickname="TestUser",
        email="test@example.com",
        provider="google"
    )
    await user_repo.create(obj_in=new_user)
    
    # Check if we can get it from the endpoint
    response = await async_client.get("/api/v1/users/test_uid_123")
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "test_uid_123"
    assert data["nickname"] == "TestUser"


async def test_login_underage_blocked(async_client: AsyncClient):
    # Try to login/register with under-14 birthdate using internal API Key (NextAuth workflow)
    payload = {
        "providerAccountId": "mock_underage_uid",
        "provider": "google",
        "birthdate": "2020-01-01T00:00:00Z"
    }
    headers = {
        "x-internal-api-key": "test_internal_api_key"
    }
    response = await async_client.post(
        "/api/v1/auth/login",
        json=payload,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "ERROR_UNDER_AGE_LIMIT"


async def test_onboard_and_adult_verification(async_client: AsyncClient):
    # 1. Create a user
    user = User(
        uid="test_onboard_user",
        nickname="OnboardMe",
        email="onboard@example.com",
        provider="google"
    )
    await user_repo.create(obj_in=user)
    
    # Generate token
    token = create_access_token(data={"sub": "test_onboard_user"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Try onboarding with age < 14
    onboard_payload_underage = {
        "nickname": "YoungUser",
        "birthdate": "2020-01-01T00:00:00Z",
        "nsfw_filter": True
    }
    response = await async_client.patch(
        "/api/v1/users/me/onboard",
        json=onboard_payload_underage,
        headers=headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "ERROR_UNDER_AGE_LIMIT"
    
    # 3. Onboard successfully with age >= 14
    onboard_payload_valid = {
        "nickname": "AdultUser",
        "birthdate": "2000-01-01T00:00:00Z",
        "nsfw_filter": False
    }
    response = await async_client.patch(
        "/api/v1/users/me/onboard",
        json=onboard_payload_valid,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "AdultUser"
    assert data["nsfwFilter"] is False
    assert data["birthdate"] is not None
    
    # 4. Adult Verification - Failure Case
    verify_payload_fail = {
        "provider": "DANAL",
        "auth_token": "fail"
    }
    response = await async_client.post(
        "/api/v1/auth/verify-adult",
        json=verify_payload_fail,
        headers=headers
    )
    assert response.status_code == 400
    
    # 5. Adult Verification - Success Case
    verify_payload_success = {
        "provider": "DANAL",
        "auth_token": "valid_token_123"
    }
    response = await async_client.post(
        "/api/v1/auth/verify-adult",
        json=verify_payload_success,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["isAdult"] is True
    assert data["adultVerifiedAt"] is not None


async def test_create_user_avatar(async_client: AsyncClient):
    # 1. Create a user
    user = User(
        uid="test_avatar_user",
        nickname="AvatarUser",
        email="avatar@example.com",
        provider="google"
    )
    await user_repo.create(obj_in=user)
    
    # Generate token
    token = create_access_token(data={"sub": "test_avatar_user"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Call avatar creation endpoint
    payload = {
        "mbti": "INFP",
        "personality_tags": ["#책벌레", "#시니컬"],
        "avatar_images": {
            "default": "default_url",
            "happy": "happy_url",
            "sad": "sad_url",
            "angry": "angry_url",
            "surprised": "surprised_url",
            "blushed": "blushed_url"
        }
    }
    
    response = await async_client.post(
        "/api/v1/users/avatar",
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "user" in data
    assert data["user"]["uid"] == "test_avatar_user"
    assert data["user"]["mbti"] == "INFP"
    
    # Verify DB state of updated user
    updated_user = await User.find_one(User.uid == "test_avatar_user")
    assert updated_user.mbti == "INFP"
    assert updated_user.personality_tags == ["#책벌레", "#시니컬"]
    assert updated_user.avatar_images.default == "default_url"


async def test_login_bootstraps_random_user_nickname_and_default_agent(async_client: AsyncClient):
    # Given: a first-time social login with deterministic random choices
    def choose(options: tuple[str, ...]) -> str:
        pool = tuple(options)
        if "반짝" in pool:
            return "별빛"
        if "고래" in pool:
            return "고래"
        if "Nova" in pool:
            return "Nova"
        if "상황을 차분하게 정리하고, 필요한 순간에만 또렷하게 개입하는 균형형 어시스턴트." in pool:
            return "상황을 차분하게 정리하고, 필요한 순간에만 또렷하게 개입하는 균형형 어시스턴트."
        if "gemini-2.0-flash" in pool:
            return "gemini-2.0-flash"
        if "female" in pool:
            return "female"
        if "INFJ" in pool:
            return "INFP"
        if "formal" in pool:
            return "warm"
        raise AssertionError(f"Unexpected random pool: {pool}")

    with patch(
        "app.services.signup_bootstrap.random.choice",
        side_effect=choose,
    ), patch("app.services.signup_bootstrap.random.randint", return_value=42):
        # When: the user logs in for the first time
        response = await async_client.post(
            "/api/v1/auth/login",
            headers={"x-internal-api-key": "test_internal_api_key"},
            json={
                "providerAccountId": "boot_uid_123",
                "provider": "google",
            },
        )

    # Then: the backend assigns a random nickname and creates one default agent
    assert response.status_code == 200
    login_data = response.json()
    assert login_data["user"]["nickname"] == "별빛고래42"

    created_user = await User.find_one(User.uid == "google:boot_uid_123")
    assert created_user is not None
    assert created_user.nickname == "별빛고래42"

    agent_response = await async_client.get(
        "/api/v1/agents/my",
        headers={"Authorization": f"Bearer {login_data['accessToken']}"},
    )
    assert agent_response.status_code == 200
    agents = agent_response.json()
    assert len(agents) == 1
    assert agents[0]["agent_name"] == "Nova"
    assert agents[0]["gender"] == "female"
    assert agents[0]["mbti_ei"] == "I"
    assert agents[0]["speaking_tone"] == "warm"

    updated_agent_response = await async_client.patch(
        f"/api/v1/agents/{agents[0]['key_id']}",
        headers={"Authorization": f"Bearer {login_data['accessToken']}"},
        json={
            "agent_name": "Luna",
            "gender": "male",
            "mbti_ei": "E",
            "speaking_tone": "formal",
        },
    )
    assert updated_agent_response.status_code == 200
    updated_agent = updated_agent_response.json()
    assert updated_agent["agent_name"] == "Luna"
    assert updated_agent["gender"] == "male"
    assert updated_agent["mbti_ei"] == "E"
    assert updated_agent["speaking_tone"] == "formal"

    # Then: the user can only own three agents total
    create_headers = {"Authorization": f"Bearer {login_data['accessToken']}"}
    for index in range(2):
        create_response = await async_client.post(
            "/api/v1/agents",
            headers=create_headers,
            json={
                "agent_name": f"Custom {index + 1}",
                "persona": "테스트 에이전트",
                "model": "gpt-4o",
                "gender": "female",
                "mbti_ei": "I",
                "mbti_sn": "N",
                "mbti_tf": "F",
                "mbti_jp": "P",
                "speaking_tone": "warm",
            },
        )
        assert create_response.status_code == 200

    blocked_response = await async_client.post(
        "/api/v1/agents",
        headers=create_headers,
        json={
            "agent_name": "Custom 3",
            "persona": "슬롯 초과 에이전트",
            "model": "gpt-4o",
        },
    )
    assert blocked_response.status_code == 409
    assert "최대 3개" in blocked_response.json()["detail"]
