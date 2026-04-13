from typing import Optional, List
from app.db.repository.base import BaseRepository
from app.models.archive import ArchivePost, ArchiveAnswer
from pydantic import BaseModel
from beanie import PydanticObjectId

class ArchivePostRepository(BaseRepository[ArchivePost, BaseModel, BaseModel]):
    def __init__(self):
        super().__init__(ArchivePost)

    async def get_by_id(self, post_id: str) -> Optional[ArchivePost]:
        try:
            return await self.model.get(PydanticObjectId(post_id))
        except Exception as e:
            import traceback
            print(f"Error in get_by_id: {e}")
            traceback.print_exc()
            raise ValueError(f"유효하지 않은 Post ID입니다. 에러: {e}")
        
    async def get_multi_by_category(self, category: str, skip: int = 0, limit: int = 100) -> List[ArchivePost]:
        """카테고리별 질문 목록 조회"""
        return await self.model.find(self.model.category == category).sort(-self.model.created_at).skip(skip).limit(limit).to_list()


class ArchiveAnswerRepository(BaseRepository[ArchiveAnswer, BaseModel, BaseModel]):
    def __init__(self):
        super().__init__(ArchiveAnswer)


archive_repo = ArchivePostRepository()
archive_answer_repo = ArchiveAnswerRepository()
