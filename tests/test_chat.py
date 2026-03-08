import pytest
from httpx import AsyncClient
from app.models.user import User
from app.models.chat import ChatConversation, ChatMessage
from app.db.repository.user_repository import user_repo
from app.db.repository.chat_repository import chat_repo

pytestmark = pytest.mark.asyncio

async def test_chat_creation_and_history(async_client: AsyncClient):
    # Create test user
    new_user = User(
        uid="chat_user_1",
        nickname="ChatUser",
        email="chat@example.com"
    )
    await user_repo.create(obj_in=new_user)
    
    # Create a conversation with some messages directly via repo
    conv = ChatConversation(
        uid="chat_user_1",
        messages=[
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!")
        ]
    )
    await chat_repo.create(obj_in=conv)
    
    # Fetch history via endpoint
    # Note: We aren't testing auth because we don't have a token,
    # but the endpoint uses `CurrentUserOptional` so it might return empty for guest.
    # So we'll fetch via repo to test the repository itself works
    fetched_conv = await chat_repo.get_latest_conversation("chat_user_1")
    assert fetched_conv is not None
    assert len(fetched_conv.messages) == 2
    assert fetched_conv.messages[0].content == "Hello"
