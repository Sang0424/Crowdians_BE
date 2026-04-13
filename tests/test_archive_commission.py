import pytest
from app.models.user import User, UserStats
from app.models.archive import ArchivePost
from app.models.mailbox import Mail
from app.services.archive_service import create_archive_post, reject_commission

@pytest.mark.asyncio
async def test_direct_commission_flow(setup_db):
    # 1. Setup users
    user1 = User(
        uid="user1_uid",
        nickname="Requester",
        provider="google",
        stats=UserStats(gold=1000)
    )
    await user1.insert()
    
    user2 = User(
        uid="user2_uid",
        nickname="Target",
        provider="google",
        stats=UserStats(gold=500)
    )
    await user2.insert()
    
    # 2. Create direct commission post
    post_id = await create_archive_post(
        user=user1,
        title="Direct Question",
        content="Please answer this",
        target_user_id="user2_uid",
        locale="ko"
    )
    
    # 3. Verify post creation and state
    post = await ArchivePost.get(post_id)
    assert post is not None
    assert post.target_user_id == "user2_uid"
    assert post.status == "commissioned"
    
    # Verify no bounty deduction (manually check)
    updated_user1 = await User.find_one(User.uid == "user1_uid")
    assert updated_user1.stats.gold == 1000
    
    # Verify mailbox message
    message = await Mail.find_one(Mail.user_id == "user2_uid")
    assert message is not None
    assert message.reference_id == post_id
    assert "Direct Question" in message.content
    
    # 4. Reject commission by user2
    success = await reject_commission(user2, post_id)
    assert success is True
    
    # 5. Verify post rejection state
    post = await ArchivePost.get(post_id)
    assert post.status == "rejected"
    
    # Verify no bounty refund to user1 since it was free
    updated_user1 = await User.find_one(User.uid == "user1_uid")
    assert updated_user1.stats.gold == 1000
