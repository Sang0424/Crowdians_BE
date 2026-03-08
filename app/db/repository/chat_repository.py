from typing import Optional
from app.db.repository.base import BaseRepository
from app.models.chat import ChatConversation
from pydantic import BaseModel

class ChatRepository(BaseRepository[ChatConversation, BaseModel, BaseModel]):
    def __init__(self):
        super().__init__(ChatConversation)

    async def get_latest_conversation(self, uid: str) -> Optional[ChatConversation]:
        """유저의 최신 대화 세션 조회"""
        return await self.model.find_one(
            self.model.uid == uid,
            sort=[("created_at", -1)]
        )

chat_repo = ChatRepository()
