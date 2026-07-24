# app/models/channel.py
"""
AI Agent 간 대화 및 브랜치(분기) 모델.

구조:
  Channel (Document)
    └── branches: dict[branch_id, Branch]   (해시트리 기반 O(1) 조회)
          └── messages: list[Message]

브랜치 ID는 SHA-256 기반 해시로 생성되어 중복 없이 무한 분기를 지원.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_branch_id(
    parent_branch_id: Optional[str],
    fork_message_id: Optional[str],
    intervention_content: Optional[str],
) -> str:
    """
    SHA-256 기반 고유 브랜치 ID 생성.
    root 브랜치는 parent=None, fork_msg=None, intervention=None 으로 호출.
    """
    raw = f"{parent_branch_id}|{fork_message_id}|{intervention_content}|{uuid.uuid4()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ─────────────────────────────────────────────
# Sub-models (embedded)
# ─────────────────────────────────────────────

class AgentProfile(BaseModel):
    """참여 AI Agent 프로필"""
    agent_id: str                       # 고유 식별자 (UUID)
    name: str                           # 에이전트 표시 이름
    persona: str                        # 시스템 프롬프트 / 역할 정의
    model: str = "gemini-2.0-flash"    # 사용할 LLM 모델
    runtime_mode: str = "platform"
    avatar_url: str = ""
    gender: str = ""
    mbti_ei: str = ""
    mbti_sn: str = ""
    mbti_tf: str = ""
    mbti_jp: str = ""
    speaking_tone: str = ""
    api_key_id: Optional[str] = None   # 외부 에이전트 연동 시 API Key 식별자


class AgentRelationship(BaseModel):
    """에이전트 쌍 간의 동적 관계 정보"""
    agent_id_a: str
    agent_id_b: str
    affinity: int = 50                      # 0 ~ 100 친밀도
    relationship_label: str = "Neutral"     # 요약 레이블
    sentiment: str = "neutral"              # "positive" | "neutral" | "negative"
    description: Optional[str] = None       # 상세 서사
    trigger_message_id: Optional[str] = None
    trigger_message_content: Optional[str] = None
    updated_at: datetime = Field(default_factory=_utcnow)


class Message(BaseModel):
    """개별 채팅 메시지"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str                       # 발화 에이전트 ID
    content: str
    detected_emotion: str = "default"   # 감지된 감정 상태 (default, happy, sad, angry, surprised, blushed)
    created_at: datetime = Field(default_factory=_utcnow)
    branch_count: int = 0              # 이 메시지에서 파생된 분기 수
    upvotes: int = 0                   # 메시지 추천수
    downvotes: int = 0                 # 메시지 비추천수


class Branch(BaseModel):
    """
    대화 분기 (해시트리의 노드).
    root branch: parent_branch_id=None, fork_message_id=None, intervention=None
    """
    branch_id: str                                  # SHA-256 기반 해시 ID
    parent_branch_id: Optional[str] = None          # 부모 분기 ID
    fork_message_id: Optional[str] = None           # 분기 시작점 메시지 ID
    channel_name: str = "general"
    intervention_type: Optional[str] = None          # "replace" | "redirect"
    intervention_content: Optional[str] = None       # 인간의 지시 내용
    intervener_uid: Optional[str] = None             # 개입한 유저 UID
    data_opt_in: bool = False                       # RLHF 데이터셋 기여 동의 여부
    rejected_content: Optional[str] = None          # Replace 개입 시 수정 전 원본 AI 발화
    child_branch_ids: list[str] = Field(default_factory=list)  # 하위 분기 IDs
    memory_candidate_ids: list[str] = Field(default_factory=list)
    safety_events: list[str] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    likes: int = 0
    scraps: int = 0
    engagement_score: float = 0.0                   # 피드 노출 우선순위 점수
    depth: int = 0                                  # 트리 깊이 (root=0)
    status: str = "active"                          # "active" | "completed"
    is_public: bool = False                         # 마켓플레이스 공개 여부
    created_at: datetime = Field(default_factory=_utcnow)


# ─────────────────────────────────────────────
# Root Document
# ─────────────────────────────────────────────

class Channel(Document):
    """
    AI Agent 대화 채널 최상위 Document.

    branches는 dict[branch_id, Branch]로 저장하여 O(1) 조회를 지원.
    root_branch_id를 통해 트리 탐색 시작점을 알 수 있다.
    """
    title: str
    topic: str
    category: str = "general"                               # 마켓플레이스 분류 카테고리
    tags: list[str] = Field(default_factory=list)           # 카테고리/태그 (필터용)
    agents: list[AgentProfile] = Field(default_factory=list)
    relationships: list[AgentRelationship] = Field(default_factory=list)
    agent_moods: dict[str, str] = Field(default_factory=dict) # agent_id -> mood emoji/label
    creator_uid: Optional[str] = None                       # 채널 생성 요청 유저 UID
    root_branch_id: str = ""
    branches: dict[str, Branch] = Field(default_factory=dict)  # branch_id → Branch
    total_likes: int = 0
    is_public: bool = False                                 # 채널 공개 여부
    status: str = "active"                                  # "active" | "completed" | "archived"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def get_branch(self, branch_id: str) -> Optional[Branch]:
        return self.branches.get(branch_id)

    def get_root_branch(self) -> Optional[Branch]:
        return self.branches.get(self.root_branch_id)

    class Settings:
        name = "channels"
