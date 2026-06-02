import pytest
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.models.conversation import Conversation, AgentProfile, Message
from app.services import conversation_service

pytestmark = pytest.mark.asyncio

async def test_channel_score_and_voting():
    # 1. Create a test user
    user = User(
        uid="test_user_score",
        nickname="ScoreTester",
        email="tester@example.com",
        provider="google"
    )
    await user.insert()

    # 2. Create a conversation
    agent1 = AgentProfile(agent_id="agent-1", name="Agent A", persona="Persona A")
    conv = await conversation_service.create_conversation(
        title="Score Test Conversation",
        topic="Resource Allocation",
        tags=["test"],
        agents=[agent1],
        creator_uid="test_user_score"
    )
    
    # Check default root branch is general
    root_branch_id = conv.root_branch_id
    assert root_branch_id != ""
    assert conv.branches[root_branch_id].channel_name == "general"
    
    # 3. Add mock message to root branch
    msg1 = Message(
        message_id="msg-test-1",
        agent_id="agent-1",
        content="Let's buy a magic shield!"
    )
    await conversation_service.add_message_to_branch(
        conversation_id=str(conv.id),
        branch_id=root_branch_id,
        message=msg1
    )
    
    # Verify message was added
    conv = await conversation_service.get_conversation(str(conv.id))
    assert len(conv.branches[root_branch_id].messages) == 1
    
    # 4. Perform voting on message
    vote_res = await conversation_service.toggle_message_vote(
        uid="test_user_score",
        conversation_id=str(conv.id),
        branch_id=root_branch_id,
        message_id="msg-test-1",
        vote_type="upvote"
    )
    assert vote_res["success"] is True
    assert vote_res["upvotes"] == 1
    assert vote_res["user_vote"] == "upvote"
    
    # Toggle off (second click)
    vote_res_off = await conversation_service.toggle_message_vote(
        uid="test_user_score",
        conversation_id=str(conv.id),
        branch_id=root_branch_id,
        message_id="msg-test-1",
        vote_type="upvote"
    )
    assert vote_res_off["upvotes"] == 0
    assert vote_res_off["user_vote"] is None

    # Vote again to keep score > 0
    await conversation_service.toggle_message_vote(
        uid="test_user_score",
        conversation_id=str(conv.id),
        branch_id=root_branch_id,
        message_id="msg-test-1",
        vote_type="upvote"
    )
    
    # 5. Add a sub branch (Channel: 'strategy')
    conv, sub_branch = await conversation_service.create_branch(
        conversation_id=str(conv.id),
        parent_branch_id=root_branch_id,
        fork_message_id="msg-test-1",
        intervention_type="redirect",
        intervention_content="Focus on defensive strategies",
        intervener_uid="test_user_score",
        channel_name="strategy"
    )
    
    # Perform like on sub branch
    like_res = await conversation_service.toggle_like(
        uid="test_user_score",
        conversation_id=str(conv.id),
        branch_id=sub_branch.branch_id
    )
    assert like_res["count"] == 1
    
    # 6. Calculate Preference Score for 'general' channel
    general_score_res = await conversation_service.calculate_channel_preference_score(
        conversation_id=str(conv.id),
        channel_name="general"
    )
    assert general_score_res["channel_name"] == "general"
    assert general_score_res["metrics"]["total_branches"] == 1
    assert general_score_res["metrics"]["total_upvotes"] == 1
    
    # 7. Calculate Preference Score for 'strategy' channel
    strategy_score_res = await conversation_service.calculate_channel_preference_score(
        conversation_id=str(conv.id),
        channel_name="strategy"
    )
    assert strategy_score_res["channel_name"] == "strategy"
    assert strategy_score_res["metrics"]["total_branches"] == 1
    assert strategy_score_res["metrics"]["total_likes"] == 1
    
    # Clean up
    await user.delete()
    await conv.delete()
