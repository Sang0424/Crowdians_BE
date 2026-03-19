# app/schemas/academy.py

from pydantic import BaseModel, Field

class StartSessionResponse(BaseModel):
    success: bool
    learningTickets: int

class KnowledgeCardResponse(BaseModel):
    id: str             # card._id 문자열
    type: str           # "vote" | "teach" | "quiz"
    question: str
    choices: list[str]
    bounty: int


class CardSubmitRequest(BaseModel):
    answer: str | int = Field(..., description="유저가 선택한/작성한 답변 (인덱스 또는 텍스트)")


class CardSubmitResponse(BaseModel):
    isCorrect: bool
    rewardExp: int
    rewardGold: int
    rewardTrust: int
    message: str


class CardRejectResponse(BaseModel):
    success: bool
    message: str


class TicketRechargeResponse(BaseModel):
    success: bool
    ticketsRemaining: int
    rechargesToday: int
    message: str
