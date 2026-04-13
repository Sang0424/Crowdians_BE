# app/schemas/adventure.py

from pydantic import BaseModel, Field


# ── 이벤트 노드 / 선택지 ──

class AdventureChoiceResponse(BaseModel):
    id: str
    text: str
    requiredStat: str   # 판정에 사용되는 스탯 이름 (courage / intelligence / trust / intimacy)


class AdventureNodeResponse(BaseModel):
    depth: int
    eventType: str
    title: str
    description: str
    choices: list[AdventureChoiceResponse]
    isCleared: bool


# ── 세션 응답 ──

class AdventureSessionResponse(BaseModel):
    sessionId: str
    hp: int
    currentDepth: int
    maxDepth: int
    status: str                         # active, complete, gameover
    currentNode: AdventureNodeResponse | None


# ── 모험 선택(Select) ──

class AdventureSelectRequest(BaseModel):
    choiceId: str = Field(..., description="유저가 고른 선택지의 ID (예: 'fight', 'run')")


class AdventureSelectResponse(BaseModel):
    success: bool                       # 행동 성공 여부 (확률 기반)
    hpLost: int                         # 잃은 체력 (0이면 피해 없음)
    rewardExp: int                      # 획득한 경험치
    rewardGold: int                     # 획득한 골드
    currentHp: int                      # 남은 체력
    status: str                         # 갱신된 세션 상태 ("active" | "gameover" | "complete")
    message: str                        # 유저에게 보여줄 결과 텍스트


# ── 모험 다음 깊이로 이동(Continue) ──

class AdventureContinueResponse(BaseModel):
    success: bool
    nextNode: AdventureNodeResponse | None
    status: str
    message: str
    rewardTickets: int | None = Field(default=None, description="10층 클리어 시 획득한 티켓")
    courageGained: int | None = Field(default=None, description="진행 층수 비례 상승한 용기 스탯")
