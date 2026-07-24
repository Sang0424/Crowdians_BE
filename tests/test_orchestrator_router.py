from langchain_core.messages import HumanMessage

from app.models.channel import AgentProfile, Branch, Channel, Message
from app.services.channel_service import get_branch_moderator_state
from app.services.orchestrator import router_node


def test_router_prefers_named_other_agent_when_allowed():
    agent_a = AgentProfile(agent_id="agent-a", name="Agent A", persona="Persona A")
    agent_b = AgentProfile(agent_id="agent-b", name="Agent B", persona="Persona B")
    branch = Branch(
        branch_id="root",
        messages=[
            Message(
                message_id="m1",
                agent_id="agent-a",
                content="Agent B, 너는 이 상황을 어떻게 보고 있어?",
            )
        ],
    )
    channel = Channel(
        title="Router test",
        topic="Routing",
        agents=[agent_a, agent_b],
        root_branch_id="root",
        branches={"root": branch},
    )
    moderator_state = get_branch_moderator_state(channel, "root")

    result = router_node(
        {
            "conversation_id": "c1",
            "current_branch_id": "root",
            "conversation": channel,
            "messages": [HumanMessage(content=branch.messages[-1].content)],
            "moderator_state": moderator_state,
            "next_speaker": None,
            "intervention": None,
        }
    )

    assert result["next_speaker"] == "agent-b"
