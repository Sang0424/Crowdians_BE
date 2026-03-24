# app/services/quest_service.py

from datetime import datetime, timezone
from beanie import PydanticObjectId
from app.models.quest import Quest, UserQuestBookmark
from app.models.user import User
from app.core.exceptions import InsufficientResourceError, NotFoundError


async def create_quest(
    user: User,
    title: str,
    description: str,
    tags: list[str],
    reward: int,
    is_sos: bool = False
) -> str:
    """새로운 의뢰 생성 및 골드 차감"""
    if reward > 0 and user.stats.gold < reward:
        raise InsufficientResourceError("골드")

    # 골드 차감
    if reward > 0:
        user.stats.gold -= reward
        # 유저 정보 업데이트 (user_repository를 쓰거나 직접 save)
        await user.save()

    # 의뢰 생성
    quest = Quest(
        title=title,
        description=description,
        tags=tags,
        reward=reward,
        is_sos=is_sos,
        author_id=user.uid
    )
    await quest.insert()
    return str(quest.id)


async def toggle_quest_bookmark(user: User, quest_id: str) -> bool:
    """의뢰/게시글 북마크 토글"""
    # 1. 대상 찾기 (Quest or ArchivePost)
    target = await Quest.get(quest_id)
    if not target:
        from app.models.archive import ArchivePost
        target = await ArchivePost.get(quest_id)
        
    if not target:
        raise NotFoundError("의뢰/게시글")

    # 2. 북마크 존재 여부 확인
    bookmark = await UserQuestBookmark.find_one(
        UserQuestBookmark.user_id == user.uid,
        UserQuestBookmark.quest_id == quest_id
    )

    if bookmark:
        # 삭제
        await bookmark.delete()
        if hasattr(target, "bookmark_count"):
            target.bookmark_count = max(0, target.bookmark_count - 1)
            await target.save()
        return False
    else:
        # 생성
        new_bookmark = UserQuestBookmark(
            user_id=user.uid,
            quest_id=quest_id
        )
        await new_bookmark.insert()
        if hasattr(target, "bookmark_count"):
            target.bookmark_count += 1
            await target.save()
        return True
