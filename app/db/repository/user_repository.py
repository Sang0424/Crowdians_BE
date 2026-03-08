from typing import Optional
from app.db.repository.base import BaseRepository
from app.models.user import User

class UserRepository(BaseRepository[User, User, User]):
    def __init__(self):
        super().__init__(User)

    async def get_by_uid(self, uid: str) -> Optional[User]:
        """UID로 유저 조회"""
        return await self.model.find_one(self.model.uid == uid)

user_repo = UserRepository()
