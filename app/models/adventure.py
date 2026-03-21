# app/models/adventure.py

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import BaseModel, Field


class AdventureChoice(BaseModel):
    """사건 내에서 유저가 선택할 수 있는 보기"""
    id: str                         # a, b, c 등
    text: str                       # 텍스트 내용
    # 범용 스탯 판정: required_stat = "courage" | "intelligence" | "trust" | "intimacy" ...
    required_stat: str = "courage"  # 판정에 사용할 스탯 이름
    stat_modifier: int = 0          # 해당 스탯에 추가되는 보정치 (양수/음수)
    hp_penalty_on_fail: int = 10    # 실패 시 잃는 HP


class AdventureNode(BaseModel):
    """모험의 한 깊이(Depth)에서 발생하는 이벤트"""
    depth: int
    event_type: str                 # "monster", "trap", "treasure", "npc" 등
    title: str                      # "오크를 만났다!" 등
    description: str                # 상황 설명 텍스트
    choices: list[AdventureChoice]  # 선택지들
    
    # 결과 처리용 상태 (이미 선택한 후에는 값이 세팅됨)
    is_cleared: bool = False
    chosen_choice_id: Optional[str] = None
    success: Optional[bool] = None


class AdventureSession(Document):
    """모험 세션"""
    user_id: str                    # User.uid
    hp: int = 100                   # 현재 체력
    current_depth: int = 1          # 현재 층수 (예: 1~10층까지 존재)
    max_depth: int = 10             # 클리어 목표 층
    
    status: str = "active"          # "active"(진행중), "complete"(클리어), "gameover"(사망)
    
    nodes: list[AdventureNode] = Field(default_factory=list)  # 층마다 발생한/할 이벤트 배열
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "adventure_sessions"
