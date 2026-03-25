# app/services/quest_service.py

from datetime import datetime, timezone
from beanie import PydanticObjectId
from app.models.quest import Quest, UserQuestBookmark
from app.models.user import User
from app.core.exceptions import InsufficientResourceError, NotFoundError
from app.services.mailbox_service import send_system_mail


async def create_quest(
    user: User,
    title: str,
    description: str,
    tags: list[str],
    reward: int,
    is_sos: bool = False,
    target_user_id: str | None = None
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
        author_id=user.uid,
        target_user_id=target_user_id
    )
    await quest.insert()

    # 대상 유저가 지정된 직접 의뢰인 경우 우편함 알림 전송
    if target_user_id:
        await send_system_mail(
            user_id=target_user_id,
            title="🎯 새로운 직접 의뢰가 도착했습니다!",
            content=f"'{user.nickname}' 크라우디언님이 당신에게 퀘스트 의뢰를 보냈습니다.\n\n제목: {title}\n내용: {description}\n보상: {reward} 골드",
            mail_type="commission_request",
            reference_id=str(quest.id)
        )

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

async def answer_quest(
    user: User,
    quest_id: str,
    content: str
) -> bool:
    """퀘스트에 대한 답변을 등록하고 원작자에게 메일을 보냅니다."""
    quest = await Quest.get(quest_id)
    if not quest:
        raise NotFoundError("의뢰(퀘스트)")

    # 1. 퀘스트에 답변 저장 (Quest 모델에 answers 필드가 있다고 가정)
    # 만약 답변을 별도의 ArchiveAnswer 모델로 관리한다면 해당 모델에 저장합니다.
    # 여기서는 간략하게 Mailbox를 통해 바로 전달하는 방식을 사용합니다.

    # 2. 원작자(의뢰자)에게 답변 완료 메일 발송
    await send_system_mail(
        user_id=quest.author_id,
        title=f"💌 '{quest.title}' 의뢰에 대한 답변이 도착했습니다!",
        content=f"'{user.nickname}' 님이 당신의 의뢰에 답변을 작성했습니다.\n\n[답변 내용]\n{content}\n\n보상: {quest.reward} 골드",
        mail_type="commission_answered", # 시스템 Enum에 맞춰 수정
        reference_id=str(quest.id)
        # 필요한 경우 보상(reward) 추가 설정
    )

    # 3. 퀘스트 상태 업데이트 (예: '완료' 상태로 변경)
    # quest.status = "completed"
    # await quest.save()

    return True