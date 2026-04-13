# app/services/adventure_service.py

import random
from datetime import datetime, timezone
from bson import ObjectId

from app.models.user import User
from app.models.adventure import AdventureSession, AdventureNode, AdventureChoice


# ── 스탯 이름 → User.stats 속성명 매핑 ──────────────────────────────────────
_STAT_ATTR_MAP: dict[str, str] = {
    "courage":      "courage",
    "intelligence": "intelligence",
    "trust":        "trust",
    "intimacy":     "intimacy",
}


def _get_stat_value(user: User, stat_name: str) -> int:
    """required_stat 이름으로 실제 유저 스탯 값을 반환. 알 수 없는 이름은 0."""
    attr = _STAT_ATTR_MAP.get(stat_name, "courage")
    return getattr(user.stats, attr, 0)


def _generate_random_node(depth: int) -> AdventureNode:
    """깊이(Depth)에 따른 랜덤 이벤트를 생성합니다."""
    templates = [
        {
            "type": "monster",
            "title": "node.monster.title",
            "desc": "node.monster.desc",
            "choices": [
                {
                    "id": "fight",
                    "text": "node.monster.fight.text",
                    "required_stat": "courage",
                    "mod": -10,
                    "penalty": 30,
                },
                {
                    "id": "run",
                    "text": "node.monster.run.text",
                    "required_stat": "courage",
                    "mod": +10,
                    "penalty": 15,
                },
            ],
        },
        {
            "type": "trap",
            "title": "node.trap.title",
            "desc": "node.trap.desc",
            "choices": [
                {
                    "id": "open",
                    "text": "node.trap.open.text",
                    "required_stat": "intelligence",
                    "mod": -20,
                    "penalty": 20,
                },
                {
                    "id": "ignore",
                    "text": "node.trap.ignore.text",
                    "required_stat": "intelligence",
                    "mod": +30,
                    "penalty": 10,
                },
            ],
        },
        {
            "type": "treasure",
            "title": "node.treasure.title",
            "desc": "node.treasure.desc",
            "choices": [
                {
                    "id": "drink",
                    "text": "node.treasure.drink.text",
                    "required_stat": "trust",
                    "mod": +20,
                    "penalty": 0,
                },
                {
                    "id": "rest",
                    "text": "node.treasure.rest.text",
                    "required_stat": "trust",
                    "mod": +30,
                    "penalty": 0,
                },
            ],
        },
        {
            "type": "npc",
            "title": "node.npc.title",
            "desc": "node.npc.desc",
            "choices": [
                {
                    "id": "trade",
                    "text": "node.npc.trade.text",
                    "required_stat": "intimacy",
                    "mod": +0,
                    "penalty": 30,
                },
                {
                    "id": "talk",
                    "text": "node.npc.talk.text",
                    "required_stat": "intimacy",
                    "mod": +20,
                    "penalty": 0,
                },
            ],
        },
    ]

    t = random.choice(templates)

    choices = [
        AdventureChoice(
            id=c["id"],
            text=c["text"],
            required_stat=c["required_stat"],
            stat_modifier=c["mod"],
            hp_penalty_on_fail=c["penalty"],
        )
        for c in t["choices"]
    ]

    return AdventureNode(
        depth=depth,
        event_type=t["type"],
        title=t["title"],
        description=t["desc"],
        choices=choices,
    )


async def start_adventure(user: User, use_buff: bool = False) -> AdventureSession:
    """새로운 모험을 시작합니다. 기존 진행중인 건 모두 실패처리하거나 무시합니다."""
    # 1. 일일 초기화 체크
    from app.services.user_service import check_daily_reset
    if check_daily_reset(user):
        await user.save()

    # 스태미나 소모 (5 소모로 상향)
    if user.stats.stamina < 5:
        raise ValueError("모험을 시작하기 위한 스태미나가 부족합니다. (5 필요)")

    # 버프 사용 시 100G 차감
    if use_buff:
        if user.stats.gold < 100:
            raise ValueError("버프를 구매하기 위한 골드가 부족합니다. (100G 필요)")
        user.stats.gold -= 100
        start_hp = 120
    else:
        start_hp = 100

    user.stats.stamina -= 5
    await user.save()

    # 1층 노드 생성
    first_node = _generate_random_node(1)

    session = AdventureSession(
        user_id=user.uid,
        hp=start_hp,
        current_depth=1,
        max_depth=10,
        status="active",
        nodes=[first_node],
    )
    await session.insert()

    return session


async def select_adventure_node(user: User, session_id: str, choice_id: str) -> dict:
    """현재 노드에서 선택지를 골라 확률 판정 및 보상/페널티를 적용합니다."""
    try:
        session = await AdventureSession.get(ObjectId(session_id))
    except Exception:
        raise ValueError("잘못된 세션 ID입니다.")

    if not session or session.user_id != user.uid:
        raise ValueError("진행 중인 모험을 찾을 수 없습니다.")

    if session.status != "active":
        raise ValueError("이미 종료된 모험입니다.")

    current_node = session.nodes[-1]
    if current_node.is_cleared:
        raise ValueError("이 층의 이벤트는 이미 해결했습니다. '다음 층 이동'을 선택해주세요.")

    # 선택지 찾기
    selected_choice = next((c for c in current_node.choices if c.id == choice_id), None)
    if not selected_choice:
        raise ValueError("잘못된 선택지입니다.")

    # ── 성공확률 계산 ───────────────────────────────────────────────────────
    # 기본 30% + (required_stat 값 // 10) + stat_modifier
    # 판정 스탯은 선택지마다 courage / intelligence / trust / intimacy 중 하나
    stat_value = _get_stat_value(user, selected_choice.required_stat)
    base_success_rate = 30
    final_rate = base_success_rate + (stat_value // 10) + selected_choice.stat_modifier

    # 최소 10%, 최대 80% 로 클램핑
    final_rate = max(10, min(80, final_rate))

    roll = random.randint(1, 100)
    is_success = roll <= final_rate

    hp_lost = 0
    reward_exp = 0
    reward_gold = 0
    msg = ""

    if is_success:
        reward_exp = 0
        reward_gold = 20
        msg = f"위기를 극복했습니다! (Gold +{reward_gold})"
    else:
        hp_lost = selected_choice.hp_penalty_on_fail
        msg = f"선택에 실패하여 체력을 {hp_lost}만큼 잃었습니다."

    # 세션 정보 업데이트
    session.hp -= hp_lost
    if session.hp <= 0:
        session.hp = 0
        session.status = "gameover"
        msg += " 모험가가 쓰러졌습니다... (Game Over)"

    current_node.is_cleared = True
    current_node.chosen_choice_id = choice_id
    current_node.success = is_success
    session.updated_at = datetime.now(timezone.utc)

    await session.save()

    # 유저 스탯 적용 (EXP/Gold 획득 시)
    if is_success:
        user.stats.exp += reward_exp
        user.stats.gold += reward_gold

        # 레벨업 판정
        user.stats.process_level_up(max_stamina=user.max_stamina)

        # 모험을 겪으며 용기 자체가 오름
        user.stats.courage += 1

        await user.save()

    return {
        "success": is_success,
        "hpLost": hp_lost,
        "rewardExp": reward_exp,
        "rewardGold": reward_gold,
        "currentHp": session.hp,
        "status": session.status,
        "message": msg,
    }


async def continue_adventure(user: User, session_id: str) -> dict:
    """해결된 이벤트를 뒤로 하고 다음 층으로 이동합니다."""
    try:
        session = await AdventureSession.get(ObjectId(session_id))
    except Exception:
        raise ValueError("잘못된 세션 ID입니다.")

    if not session or session.user_id != user.uid:
        raise ValueError("진행 중인 모험을 찾을 수 없습니다.")

    if session.status != "active":
        raise ValueError("진행 가능한 모험이 아닙니다.")

    current_node = session.nodes[-1]
    if not current_node.is_cleared:
        raise ValueError("현재 층의 이벤트를 먼저 해결해야 합니다.")

    # 1. 10층(max_depth)을 넘겼는지 체크
    if session.current_depth >= session.max_depth:
        # 모험 클리어!
        session.status = "complete"
        session.updated_at = datetime.now(timezone.utc)
        await session.save()

        # 클리어 추가 보상 (확정 보상)
        reward_tickets = 1
        courage_gained = 1
        reward_gold = 100

        user.stats.gold += reward_gold
        user.stats.learning_tickets += reward_tickets
        user.stats.courage += courage_gained
        await user.save()

        return {
            "success": True,
            "nextNode": None,
            "status": "complete",
            "message": "축하합니다! 모험을 무사히 완료했습니다. (Ticket +1, Gold +100)",
            "rewardTickets": reward_tickets,
            "courageGained": courage_gained,
        }

    # 2. 다음 층 이벤트 스폰
    session.current_depth += 1
    new_node = _generate_random_node(session.current_depth)
    session.nodes.append(new_node)

    session.updated_at = datetime.now(timezone.utc)
    await session.save()

    node_response = {
        "depth": new_node.depth,
        "eventType": new_node.event_type,
        "title": new_node.title,
        "description": new_node.description,
        "choices": [
            {"id": c.id, "text": c.text, "requiredStat": c.required_stat}
            for c in new_node.choices
        ],
        "isCleared": new_node.is_cleared,
    }

    return {
        "success": True,
        "nextNode": node_response,
        "status": "active",
        "message": f"{session.current_depth}층으로 진입했습니다.",
    }
