# app/services/dpo_service.py
import re
from datetime import datetime
from typing import Any, Dict, List
from app.models.channel import Channel

# --- Regex patterns for PII Masking ---
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9\._%+-]+@[a-zA-Z0-9\.-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(r'(?:\+82|0)(?:1[0-9]|[2-8][0-9]?)-?[0-9]{3,4}-?[0-9]{4}')

# Korean Address Regex (Matches addresses starting with major provinces/cities)
ADDRESS_REGEX = re.compile(
    r'(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)'
    r'[가-힣\s]*(?:시|도|군|구|읍|면|동|리|로|길)\s?'
    r'(?:\d+[-\d\s]*\d+|\d+)?'
)

# Korean Name Regex
# 2 to 3 characters starting with common Korean surnames, followed by common particles/honorifics or a word boundary.
COMMON_SURNAMES = '김이박최정강조윤장임한오서신권황안송전홍유고문양손배조백허유남심노하곽성차구우주임임'
NAME_REGEX = re.compile(
    rf'\b([{COMMON_SURNAMES}][가-힣]{{1,2}})'
    r'(?=님|이|가|은|는|을|를|의|과|와|으로|로|이다|입니다|했다|한다|하고|하고|한테|에게|에서|\b)'
)

# Exclude common Korean words that might match the name pattern to avoid over-masking
COMMON_EXCLUSIONS = {
    "이것", "정말", "하면", "가지", "우리", "나라", "사람", "사회", "생각", "하루",
    "하나", "박수", "강물", "강산", "조선", "백성", "윤리", "장소", "임시", "한문",
    "오직", "서류", "신문", "권리", "황금", "전혀", "홍보", "유도", "고민", "문화",
    "양식", "손길", "백화", "허가", "사실", "서로", "사랑", "하늘", "자기", "사건",
    "이름", "입니다", "있습니다", "합니다", "했다", "한다", "어떻게", "이렇게",
    "저렇게", "아니다", "임니다", "이군요", "이네요", "이라서", "이므로", "이거나",
    "이든지", "이랑", "이나", "이야", "이여", "이의", "이로", "이와", "이유", "이후",
    "이전", "이미", "이마", "이빨", "이웃", "이익", "이용", "이해", "이동", "이론",
    "이상", "이하", "이외", "이지", "일부", "일반", "일단", "일찍", "일어", "일정",
    "일기", "임무", "임금", "임차", "입구", "입력", "입장", "입수", "입고", "입정",
    "한글", "한국", "한번", "한두", "한편", "한쪽", "한계", "한우", "한파", "한옥",
    "오후", "오전", "오늘", "오빠", "오해", "오류", "오염", "오직", "오리", "오락",
    "서점", "서부", "서쪽", "서명", "서구", "서로", "서류", "서명", "서비스", "서버",
    "신호", "신발", "신체", "신부", "신랑", "신뢰", "신청", "신고", "신용", "신제품",
    "권력", "권한", "권투", "권유", "권장", "권익", "권세", "권역", "권고", "권외",
    "황제", "황토", "황소", "황혼", "황해", "황사", "황홀", "황폐", "황금", "황도",
    "안녕", "안전", "안내", "안개", "안경", "안건", "안방", "안쪽", "안도", "안부",
    "송이", "송금", "송신", "송하", "송수", "송장", "송치", "송덕", "송별", "송문",
    "전부", "전체", "전화", "전국", "전문", "전략", "전기", "전쟁", "전철", "전망",
    "홍수", "홍차", "홍길", "홍보", "홍콩", "홍역", "홍조", "홍반", "홍삼", "홍익",
    "유도", "유명", "유리", "유지", "유행", "유튜브", "유저", "유일", "유용", "유쾌"
}

def mask_pii(text: str) -> str:
    """Mask personally identifiable information (PII) using regex."""
    if not text:
        return text

    # 1. Mask Email
    text = EMAIL_REGEX.sub('[EMAIL]', text)

    # 2. Mask Phone
    text = PHONE_REGEX.sub('[PHONE]', text)

    # 3. Mask Address
    text = ADDRESS_REGEX.sub('[ADDRESS]', text)

    # 4. Mask Names (preserving trailing particles/honorifics via lookahead)
    def replace_name(match):
        name_part = match.group(1)
        if name_part in COMMON_EXCLUSIONS:
            return name_part
        
        # Check if stripping common particles/honorifics makes it an excluded word
        for particle in ["님", "이", "가", "은", "는", "을", "를", "의", "과", "와", "로", "이고", "이다", "합니다", "입니다"]:
            if name_part.endswith(particle):
                stem = name_part[:-len(particle)]
                if stem in COMMON_EXCLUSIONS or stem == "":
                    return name_part
                    
        return '[NAME]'

    text = NAME_REGEX.sub(replace_name, text)

    return text


async def export_dpo_dataset() -> List[Dict[str, Any]]:
    """
    Query MongoDB 'channels' collection and collect branches where
    'data_opt_in == True' and 'intervention_type == "replace"'.
    Extract and return DPO training pairs after PII masking.
    """
    channels = await Channel.find_all().to_list()
    
    dpo_pairs = []
    for channel in channels:
        for branch_id, branch in channel.branches.items():
            if branch.data_opt_in and branch.intervention_type == "replace":
                raw_messages = branch.messages or []
                prompt_messages = []
                for msg in raw_messages:
                    created_at_val = msg.created_at
                    created_at_str = None
                    if isinstance(created_at_val, datetime):
                        created_at_str = created_at_val.isoformat()
                    elif created_at_val:
                        created_at_str = str(created_at_val)

                    prompt_messages.append({
                        "message_id": msg.message_id,
                        "agent_id": msg.agent_id,
                        "content": mask_pii(msg.content or ""),
                        "created_at": created_at_str
                    })
                    
                rejected = mask_pii(branch.rejected_content or "")
                chosen = mask_pii(branch.intervention_content or "")
                
                dpo_pairs.append({
                    "prompt": prompt_messages,
                    "rejected": rejected,
                    "chosen": chosen
                })
                
    return dpo_pairs

