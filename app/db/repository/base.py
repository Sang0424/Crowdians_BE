from typing import Generic, TypeVar, Type, Optional, List, Any
from beanie import Document
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=Document)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD 객체 초기화.
        :param model: Beanie Document 모델.
        """
        self.model = model

    async def get(self, id: Any) -> Optional[ModelType]:
        """주어진 ID(기본키 _id)로 단일 문서를 조회합니다."""
        return await self.model.get(id)

    async def get_by(self, **kwargs) -> Optional[ModelType]:
        """특정 필드 조건으로 단일 문서를 조회합니다."""
        return await self.model.find_one(kwargs)

    async def get_multi(self, skip: int = 0, limit: int = 100, sort: Any = None) -> List[ModelType]:
        """여러 문서를 조회합니다."""
        query = self.model.find_all().skip(skip).limit(limit)
        if sort:
            query = query.sort(sort)
        return await query.to_list()

    async def create(self, *, obj_in: CreateSchemaType | dict) -> ModelType:
        """새 문서를 생성합니다."""
        if isinstance(obj_in, dict):
            obj_data = obj_in
        else:
            obj_data = obj_in.model_dump()
            
        db_obj = self.model(**obj_data)
        return await db_obj.insert()

    async def update(
        self, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict
    ) -> ModelType:
        """기존 문서를 업데이트합니다."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        return await db_obj.save()

    async def delete(self, *, db_obj: ModelType) -> None:
        """문서를 삭제합니다."""
        await db_obj.delete()
