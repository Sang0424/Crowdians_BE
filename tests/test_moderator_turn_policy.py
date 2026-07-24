import pytest

from app.models.channel import AgentProfile, Message
from app.services import channel_service

pytestmark = pytest.mark.asyncio


async def test_short_followup_turn_is_allowed_once():
    agent_a = AgentProfile(agent_id="agent-a", name="Agent A", persona="Persona A")
    agent_b = AgentProfile(agent_id="agent-b", name="Agent B", persona="Persona B")

    channel = await channel_service.create_channel(
        title="Moderator turn policy",
        topic="Test follow-up turns",
        tags=["test"],
        agents=[agent_a, agent_b],
    )

    branch_id = channel.root_branch_id

    await channel_service.add_message_to_branch(
        channel_id=str(channel.id),
        branch_id=branch_id,
        message=Message(message_id="m1", agent_id="agent-a", content="잠깐, 그건 왜 그렇게 본 거야?"),
    )

    channel = await channel_service.get_channel(str(channel.id))
    moderator_state = channel_service.get_branch_moderator_state(channel, branch_id)

    assert moderator_state.next_speaker_id == "agent-a"
    assert moderator_state.allowed_speaker_ids == ["agent-a", "agent-b"]
    assert moderator_state.consecutive_turn_count == 1

    await channel_service.add_message_to_branch(
        channel_id=str(channel.id),
        branch_id=branch_id,
        message=Message(message_id="m2", agent_id="agent-a", content="내 말은, 결론을 서두를 이유가 없다는 거야."),
    )

    channel = await channel_service.get_channel(str(channel.id))
    moderator_state = channel_service.get_branch_moderator_state(channel, branch_id)

    assert moderator_state.consecutive_turn_count == 2

    await channel.delete()


async def test_third_consecutive_turn_is_blocked():
    agent_a = AgentProfile(agent_id="agent-a", name="Agent A", persona="Persona A")
    agent_b = AgentProfile(agent_id="agent-b", name="Agent B", persona="Persona B")

    channel = await channel_service.create_channel(
        title="Moderator turn policy hard cap",
        topic="Test repeated speaker cap",
        tags=["test"],
        agents=[agent_a, agent_b],
    )

    branch_id = channel.root_branch_id

    await channel_service.add_message_to_branch(
        channel_id=str(channel.id),
        branch_id=branch_id,
        message=Message(message_id="m1", agent_id="agent-a", content="지금 바로 대답해줘?"),
    )
    await channel_service.add_message_to_branch(
        channel_id=str(channel.id),
        branch_id=branch_id,
        message=Message(message_id="m2", agent_id="agent-a", content="좋아, 내가 먼저 맥락을 더 붙일게."),
    )

    with pytest.raises(ValueError, match="too many consecutive turns"):
        await channel_service.add_message_to_branch(
            channel_id=str(channel.id),
            branch_id=branch_id,
            message=Message(message_id="m3", agent_id="agent-a", content="그리고 이것까지 꼭 들어야 해."),
        )

    await channel.delete()
