# app/schemas/user.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── 공통 스탯/캐릭터 (auth.py에서 재사용) ──

class UserStatsResponse(BaseModel):
    level: int
    exp: int
    maxExp: int
    gold: int
    stamina: int
    maxStamina: int
    trust: int
    intelligence: int
    courage: int
    intimacy: int
    dailyChatExp: int
    dailyPetCount: int
    isOnboardingDone: bool
    learningTickets: int
    maxLearningTickets: int

class GuestStatsSyncRequest(BaseModel):
    exp_gained: int
    stamina_consumed: int
    intimacy_gained: int


class EquippedPartsResponse(BaseModel):
    head: str
    hand: str
    body: str
    effect: str


class CharacterResponse(BaseModel):
    type: str
    equippedParts: EquippedPartsResponse
    unlockedParts: list[str]


# ── 유저 프로필 (공개) ──

class UserProfileResponse(BaseModel):
    """다른 유저의 공개 프로필 (민감 정보 제외)"""
    uid: str
    nickname: str
    stats: UserStatsResponse
    character: CharacterResponse
    createdAt: datetime


# ── 유저 활동 탭 ──

class ActivityAnswerItem(BaseModel):
    """내가 작성한 답변"""
    answerId: str
    question: str
    answerPreview: str
    trustCount: int
    createdAt: datetime


class ActivityQuestionItem(BaseModel):
    """내가 작성한 질문"""
    questionId: str
    question: str
    answerCount: int
    bounty: int
    createdAt: datetime


class ActivitySavedItem(BaseModel):
    """저장한 항목"""
    itemId: str
    type: str           # "answer" | "question"
    question: str
    preview: str
    createdAt: datetime


class ActivityVotedItem(BaseModel):
    """투표(신뢰함)한 항목"""
    answerId: str
    question: str
    trustCount: int
    createdAt: datetime


class UserActivitiesResponse(BaseModel):
    tab: str            # answered | asked | saved | voted
    items: list         # 탭에 따라 다른 타입
    total: int
    page: int
    limit: int


# ── 회원탈퇴 ──

class DeleteAccountResponse(BaseModel):
    success: bool
    message: str


# ── 캐릭터 설정 ──

class CharacterTypeUpdateRequest(BaseModel):
    """캐릭터 타입 업데이트 요청"""
    type: str
