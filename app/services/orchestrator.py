import operator
from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.models.channel import Channel
from app.services.channel_service import ModeratorState, advance_moderator_state


class AgentState(TypedDict):
    conversation_id: str
    current_branch_id: str
    conversation: Channel
    messages: Annotated[Sequence[BaseMessage], operator.add]
    moderator_state: ModeratorState
    next_speaker: Optional[str]
    intervention: Optional[str]


def router_node(state: AgentState) -> dict[str, Optional[str]]:
    moderator_state = state["moderator_state"]

    if state.get("intervention"):
        return {"next_speaker": "human_intervention_processor"}

    if moderator_state.status != "active":
        return {"next_speaker": None}

    return {"next_speaker": _select_next_speaker(state)}


def _select_next_speaker(state: AgentState) -> Optional[str]:
    moderator_state = state["moderator_state"]
    allowed_speaker_ids = moderator_state.allowed_speaker_ids
    if not allowed_speaker_ids:
        return moderator_state.next_speaker_id

    branch = state["conversation"].branches.get(state["current_branch_id"])
    if not branch or not branch.messages:
        return allowed_speaker_ids[0]

    agent_name_by_id = {
        agent.agent_id: agent.name.lower()
        for agent in state["conversation"].agents
    }
    last_message = branch.messages[-1]
    last_content = last_message.content.lower()
    preferred_speaker_id = moderator_state.next_speaker_id

    scored_candidates = []
    for speaker_id in allowed_speaker_ids:
        score = 0
        if speaker_id == preferred_speaker_id:
            score += 4
        if speaker_id != moderator_state.last_speaker_id:
            score += 2
        speaker_name = agent_name_by_id.get(speaker_id, "")
        if speaker_name and speaker_name in last_content:
            score += 3
        if last_content.endswith(("?", "?!")) and speaker_id != moderator_state.last_speaker_id:
            score += 1
        scored_candidates.append((score, speaker_id))

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    return scored_candidates[0][1]


def generate_agent_response(
    state: AgentState,
) -> dict[str, list[BaseMessage] | ModeratorState | Optional[str]]:
    speaker = state.get("next_speaker")
    if not speaker:
        return {}

    updated_moderator_state = advance_moderator_state(
        channel=state["conversation"],
        branch_id=state["current_branch_id"],
        speaker_id=speaker,
    )
    response_message = AIMessage(content=f"{speaker} response placeholder", name=speaker)
    return {
        "messages": [response_message],
        "moderator_state": updated_moderator_state,
    }


def human_intervention_processor(
    state: AgentState,
) -> dict[str, list[BaseMessage] | ModeratorState | Optional[str]]:
    intervention = state.get("intervention")
    if not intervention:
        return {"intervention": None}

    return {
        "intervention": None,
        "messages": [HumanMessage(content=f"[Intervention] {intervention}")],
    }


def route_after_router(state: AgentState) -> str:
    next_speaker = state.get("next_speaker")
    if next_speaker == "human_intervention_processor":
        return "human_intervention"
    if next_speaker:
        return "generate_response"
    return END


def create_orchestrator_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("router", router_node)
    workflow.add_node("generate_response", generate_agent_response)
    workflow.add_node("human_intervention", human_intervention_processor)
    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "human_intervention": "human_intervention",
            "generate_response": "generate_response",
            END: END,
        },
    )
    workflow.add_edge("generate_response", "router")
    workflow.add_edge("human_intervention", "router")
    return workflow.compile(checkpointer=MemorySaver())


orchestrator_app = create_orchestrator_graph()
