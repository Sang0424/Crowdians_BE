# app/schemas/academy.py

from pydantic import BaseModel, Field

class StartSessionResponse(BaseModel):
    success: bool
    learningTickets: int

class KnowledgeCardResponse(BaseModel):
    id: str             # card._id 문자열
    type: str           # "vote" | "teach" | "quiz"
    question: str
    content: str | None = None
    summary: str | None = None
    choices: list[str]
    chat_context: list[dict] = []


class CardSubmitRequest(BaseModel):
    answer: str | int | None = Field(None, description="유저가 선택한/작성한 답변 (인덱스 또는 텍스트)")
    chosen_answer: str | int | None = Field(None, description="A/B 테스트에서 선택한 답변")
    unchosen_answer: str | int | None = Field(None, description="A/B 테스트에서 선택하지 않은 답변")


class CardSubmitResponse(BaseModel):
    isCorrect: bool
    rewardExp: int
    rewardGold: int
    rewardTrust: int
    rewardIntelligence: int
    message: str


class CardRejectResponse(BaseModel):
    success: bool
    message: str


class GuestAcademySyncItem(BaseModel):
    card_id: str
    answer: str | int | None = None
    chosen_answer: str | int | None = None
    unchosen_answer: str | int | None = None
    is_correct: bool = True
    reward_exp: int = 0
    reward_gold: int = 0
    reward_trust: int = 0
    reward_intelligence: int = 0
    stats_synced: bool = False

class GuestAcademySyncRequest(BaseModel):
    items: list[GuestAcademySyncItem]

