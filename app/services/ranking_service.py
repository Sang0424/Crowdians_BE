# app/services/ranking_service.py

from app.models.user import User

async def get_top_rankings_by_type(ranking_type: str, limit: int = 50) -> list[User]:
    """
    주어진 타입에 따라 랭킹 내역을 조회합니다.
    지원 타입: "exp" (레벨 기준, 경험치 포함), "trust" (신뢰함), "gold" 등
    """
    # 기본 정렬 필드
    sort_field = "-stats.exp" 
    
    if ranking_type == "exp":
        # 레벨이 높거나 레벨이 같으면 남은 경험치가 높은 순
        sort_field = ["-stats.level", "-stats.exp"]
    elif ranking_type == "trust":
        sort_field = "-stats.trust"
    elif ranking_type == "gold":
        sort_field = "-stats.gold"
    elif ranking_type == "courage":
        sort_field = "-stats.courage"
    else:
        raise ValueError("지원하지 않는 랭킹 타입입니다.")
        
    # User 컬렉션에서 해당 스탯을 기준으로 내림차순 정렬 후 Limit 만큼 반환
    # (만약 sort_field가 list면 MongoDB PyMongo 정렬 문법으로 적용)
    
    query = User.find_all()
    
    if isinstance(sort_field, list):
        query = query.sort(*sort_field)
    else:
        query = query.sort(sort_field)
        
    users = await query.limit(limit).to_list()
    return users
