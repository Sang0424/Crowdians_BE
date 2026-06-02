# app/services/orchestrator.py
from typing import TypedDict, Annotated, Sequence, Optional
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# ─────────────────────────────────────────────
# State Definition
# ─────────────────────────────────────────────
class AgentState(TypedDict):
    conversation_id: str
    current_branch_id: str
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_speaker: Optional[str]
    # 유저의 개입 여부/내용 (Human-in-the-loop)
    intervention: Optional[str]

# ─────────────────────────────────────────────
# Node Functions
# ─────────────────────────────────────────────
def router_node(state: AgentState):
    """
    중앙 라우터 역할.
    다음 발화할 에이전트를 결정하거나, 루프를 감지하고, 대화를 제어합니다.
    (실제로는 LLM 호출을 통해 동적으로 결정하거나 룰 기반으로 순환시킬 수 있습니다.)
    """
    # 임시 로직: 에이전트 간 핑퐁을 하거나, 종료.
    # 현재 참여한 에이전트 목록은 DB의 conversation에서 가져와야 하지만,
    # 데모/뼈대 목적이므로 상태를 업데이트하여 다음 에이전트로 라우팅하는 역할만 선언.
    
    # 만약 유저 개입이 있다면, 우선 처리.
    if state.get("intervention"):
        return {"next_speaker": "human_intervention_processor"}
    
    # TODO: LLM Evaluator를 통한 분기 제어 로직 (Bounty 등)
    next_speaker = "agent_1" # 예시 라우팅 로직
    return {"next_speaker": next_speaker}

def generate_agent_response(state: AgentState):
    """
    선택된 에이전트(next_speaker)가 발화하는 노드.
    해당 에이전트의 페르소나를 반영하여 LLM을 호출합니다.
    """
    speaker = state.get("next_speaker")
    # 실제로는 LLM 호출 후 반환된 응답을 추가
    response_msg = AIMessage(content=f"{speaker} response placeholder", name=speaker)
    return {"messages": [response_msg]}

def human_intervention_processor(state: AgentState):
    """
    유저가 대화에 개입(Fork/Redirect)했을 때,
    현재 컨텍스트를 파악하고 새로운 브랜치를 생성하기 전의 전처리 역할을 합니다.
    """
    intervention = state.get("intervention")
    # 개입 처리 로직 (DB 브랜치 분기 등은 별도 Service에서 처리)
    # 여기서는 상태 업데이트
    return {"intervention": None, "messages": [HumanMessage(content=f"[Intervention] {intervention}")]}

def route_after_router(state: AgentState):
    """라우터 결정에 따라 다음 실행할 노드를 반환"""
    next_speaker = state.get("next_speaker")
    if next_speaker == "human_intervention_processor":
        return "human_intervention"
    elif next_speaker:
        return "generate_response"
    return END

# ─────────────────────────────────────────────
# Graph Construction
# ─────────────────────────────────────────────
def create_orchestrator_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("generate_response", generate_agent_response)
    workflow.add_node("human_intervention", human_intervention_processor)
    
    # 엣지 연결 (엔트리 포인트는 라우터)
    workflow.set_entry_point("router")
    
    # 조건부 라우팅
    workflow.add_conditional_edges("router", route_after_router, {
        "human_intervention": "human_intervention",
        "generate_response": "generate_response",
        END: END
    })
    
    # 응답 생성 후 다시 라우터로 돌아감 (무한 루프 방지 로직 필요)
    workflow.add_edge("generate_response", "router")
    workflow.add_edge("human_intervention", "router")
    
    # 메모리 세이버 (Interrupt 지원)
    memory = MemorySaver()
    
    # 컴파일 시, 특정 노드 이전에 interrupt 할지 설정할 수 있음.
    # 예: 라우터가 결정한 뒤 사용자 확인을 받기 위해 interrupt_before=["generate_response"]
    app = workflow.compile(checkpointer=memory)
    return app

orchestrator_app = create_orchestrator_graph()
