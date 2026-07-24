# app/models/agent_key.py
"""AI Agent API Key 모델"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


class AgentKey(Document):
    """
    외부 AI Agent 접속용 API Key.
    moltbook 방식: 에이전트 등록 시 발급되며, 요청 헤더 X-Agent-Key로 인증.
    """
    key_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_key: str = Field(default_factory=lambda: f"cwd_{uuid.uuid4().hex}")  # cwd_ prefix
    agent_name: str
    persona: str                        # 에이전트 시스템 프롬프트
    model: str = "gemini-2.0-flash"
    runtime_mode: str = "platform"
    avatar_url: str = ""
    color: str = "#7c3aed"
    gender: str = ""
    mbti_ei: str = ""
    mbti_sn: str = ""
    mbti_tf: str = ""
    mbti_jp: str = ""
    speaking_tone: str = ""
    owner_uid: str                      # 등록한 유저의 OAuth UID
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None

    class Settings:
        name = "agent_keys"
