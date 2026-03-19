# app/services/adventure_service.py

import random
from datetime import datetime, timezone
from bson import ObjectId

from app.models.user import User
from app.models.adventure import AdventureSession, AdventureNode, AdventureChoice


def _generate_random_node(depth: int) -> AdventureNode:
    """깊이(Depth)에 따른 랜덤 이벤트를 생성합니다."""
    # 간단한 이벤트 템플릿들
    templates = [
        {
            "type": "monster",
            "title": "야생의 고블린 무리!",
            "desc": "어두운 골목에서 고블린 무리가 나타났다.",
            "choices": [
                {"id": "fight", "text": "정면 돌파한다!", "mod": -10, "penalty": 20},
                {"id": "run", "text": "재빠르게 도망친다.", "mod": +20, "penalty": 5},
            ]
        },
        {
            "type": "trap",
            "title": "수상한 보물상자",
            "desc": "길 한가운데에 빛나는 보물상자가 놓여있다.",
            "choices": [
                {"id": "open", "text": "당장 열어본다.", "mod": -20, "penalty": 30},
                {"id": "ignore", "text": "무시하고 지나간다.", "mod": +50, "penalty": 0},
            ]
        },
        {
            "type": "treasure",
            "title": "요정의 샘물",
            "desc": "지친 몸을 뉘일 수 있는 맑은 샘물을 발견했다.",
            "choices": [
                {"id": "drink", "text": "물을 마신다.", "mod": +30, "penalty": 0},
                {"id": "rest", "text": "샘물 옆에서 잠시 쉰다.", "mod": +40, "penalty": 0},
            ]
        }
    ]
    
    t = random.choice(templates)
    
    choices = [
        AdventureChoice(
            id=c["id"],
            text=c["text"],
            courage_modifier=c["mod"],
            hp_penalty_on_fail=c["penalty"]
        ) for c in t["choices"]
    ]
    
    return AdventureNode(
        depth=depth,
        event_type=t["type"],
        title=t["title"],
        description=t["desc"],
        choices=choices,
    )


async def start_adventure(user: User) -> AdventureSession:
    """새로운 모험을 시작합니다. 기존 진행중인 건 모두 실패처리하거나 무시합니다."""
    # 1. 일일 초기화 체크
    from app.services.user_service import check_daily_reset
    if check_daily_reset(user):
        await user.save()
        
    # 기존 active 세션이 있다면 그냥 놔두거나 gameover 처리 가능.
    # 여기서는 그냥 새로 덮어쓰기 위해 새 문서를 만듭니다.
    
    # 스태미나 또는 골드 소모 기획이 있다면 여기서 차감
    if user.stats.stamina < 1:
        raise ValueError("모험을 시작하기 위한 스태미나가 부족합니다. (1 필요)")
        
    user.stats.stamina -= 1
    await user.save()
    
    # 1층 노드 생성
    first_node = _generate_random_node(1)
    
    session = AdventureSession(
        user_id=user.uid,
        hp=100,
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
        
    # 성공확률 계산 (기본 50% + 용기/10 + 선택지 보정치)
    # 기획에 따라 공식은 매우 다양해질 수 있습니다.
    base_success_rate = 50
    final_rate = base_success_rate + (user.stats.courage // 10) + selected_choice.courage_modifier
    
    # 최소/최대 확률 보정
    final_rate = max(5, min(95, final_rate))
    
    # 1~100 랜덤 주사위 (주사위 값이 확률보다 작거나 같으면 성공)
    roll = random.randint(1, 100)
    is_success = roll <= final_rate
    
    hp_lost = 0
    reward_exp = 0
    reward_gold = 0
    msg = ""
    
    if is_success:
        # 성공 시 보상
        reward_exp = random.randint(5, 15)
        reward_gold = random.randint(10, 30)
        msg = f"위기를 극복했습니다! (EXP +{reward_exp}, Gold +{reward_gold})"
    else:
        # 실패 시 페널티
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
        if user.stats.exp >= user.stats.max_exp:
            user.stats.exp -= user.stats.max_exp
            user.stats.level += 1
            
        # 모험을 겪으며 용기 자체가 오름 (기획 예시)
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
        
        # 클리어 추가 보상 가능
        user.stats.gold += 100
        await user.save()
        
        return {
            "success": True,
            "nextNode": None,
            "status": "complete",
            "message": "축하합니다! 모험을 무사히 완료했습니다. 특별 클리어 보상을 지급합니다.",
        }
        
    # 2. 다음 층 몹/이벤트 스폰
    session.current_depth += 1
    new_node = _generate_random_node(session.current_depth)
    session.nodes.append(new_node)
    
    session.updated_at = datetime.now(timezone.utc)
    await session.save()
    
    # 스키마(응답)용 컨버팅
    node_response = {
        "depth": new_node.depth,
        "eventType": new_node.event_type,
        "title": new_node.title,
        "description": new_node.description,
        "choices": [
            {"id": c.id, "text": c.text} for c in new_node.choices
        ],
        "isCleared": new_node.is_cleared
    }
    
    return {
        "success": True,
        "nextNode": node_response,
        "status": "active",
        "message": f"{session.current_depth}층으로 진입했습니다."
    }
