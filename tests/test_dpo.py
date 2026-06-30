# tests/test_dpo.py
import pytest
from httpx import AsyncClient
from datetime import datetime, timezone

from app.models.user import User
from app.models.channel import Channel, Branch, Message
from app.services.dpo_service import mask_pii, export_dpo_dataset
from app.core.security import create_access_token


def test_mask_pii():
    # 1. Email masking
    assert mask_pii("Contact me at test@example.com.") == "Contact me at [EMAIL]."
    
    # 2. Phone masking
    assert mask_pii("Call 010-1234-5678 or 02-987-6543") == "Call [PHONE] or [PHONE]"
    
    # 3. Address masking
    assert mask_pii("I live in 서울시 마포구 백범로 35.") == "I live in [ADDRESS]."
    assert mask_pii("Address is 경기도 성남시 분당구 판교역로 235 12-3") == "Address is [ADDRESS]"

    # 4. Name masking (and exclusions)
    assert mask_pii("김철수님 안녕하세요.") == "[NAME]님 안녕하세요."
    assert mask_pii("이것은 정말 중요한 사실입니다.") == "이것은 정말 중요한 사실입니다."  # Excluded words not masked
    assert mask_pii("홍길동과 박지성") == "[NAME]과 [NAME]"


@pytest.mark.asyncio
async def test_export_dpo_dataset_and_api(async_client: AsyncClient):
    # 1. Clean up users & channels collections
    await User.find_all().delete()
    await Channel.find_all().delete()

    # 2. Create users (Admin and Regular User)
    admin_user = User(
        uid="admin-123",
        email="admin@test.com",
        nickname="Admin",
        provider="google",
        role="admin"
    )
    await admin_user.insert()

    regular_user = User(
        uid="user-123",
        email="user@test.com",
        nickname="User",
        provider="google",
        role="user"
    )
    await regular_user.insert()

    # 3. Mock a channel with multiple branches
    # Branch A: data_opt_in == True, intervention_type == "replace" (Should be exported)
    # Branch B: data_opt_in == False, intervention_type == "replace" (Should NOT be exported)
    # Branch C: data_opt_in == True, intervention_type == "redirect" (Should NOT be exported)
    
    msg1 = Message(message_id="msg-1", agent_id="agent-a", content="Hello, contact me at info@test.com")
    msg2 = Message(message_id="msg-2", agent_id="agent-b", content="Hi, my name is 김철수")

    branch_a = Branch(
        branch_id="branch-a",
        data_opt_in=True,
        intervention_type="replace",
        intervention_content="수정된 답변: 내 이름은 [NAME]이고 메일은 [EMAIL]입니다.",
        rejected_content="원본 답변: 내 이름은 김철수이고 메일은 info@test.com입니다.",
        messages=[msg1, msg2]
    )

    branch_b = Branch(
        branch_id="branch-b",
        data_opt_in=False,
        intervention_type="replace",
        intervention_content="Should not export",
        rejected_content="Because opt-in is false",
        messages=[msg1]
    )

    branch_c = Branch(
        branch_id="branch-c",
        data_opt_in=True,
        intervention_type="redirect",
        intervention_content="Should not export",
        rejected_content="Because type is redirect",
        messages=[msg1]
    )

    conv = Channel(
        title="DPO Test Conversation",
        topic="Testing DPO",
        branches={
            "branch-a": branch_a,
            "branch-b": branch_b,
            "branch-c": branch_c
        },
        root_branch_id="branch-b"
    )
    await conv.insert()

    # 4. Test service layer directly
    dpo_dataset = await export_dpo_dataset()
    assert len(dpo_dataset) == 1
    pair = dpo_dataset[0]
    
    # Verify PII masking in prompt
    assert pair["prompt"][0]["content"] == "Hello, contact me at [EMAIL]"
    assert pair["prompt"][1]["content"] == "Hi, my name is [NAME]"
    
    # Verify PII masking in chosen & rejected
    assert pair["rejected"] == "원본 답변: 내 이름은 [NAME]이고 메일은 [EMAIL]입니다."
    assert pair["chosen"] == "수정된 답변: 내 이름은 [NAME]이고 메일은 [EMAIL]입니다."

    # 5. Generate Auth Headers
    admin_token = create_access_token({"sub": admin_user.uid})
    user_token = create_access_token({"sub": regular_user.uid})

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # 6. Test API access (Forbidden for regular user)
    res_user = await async_client.get("/api/v1/dpo/export", headers=user_headers)
    assert res_user.status_code == 403

    # 7. Test API access (Successful for admin - format: json)
    res_admin_json = await async_client.get("/api/v1/dpo/export?format=json", headers=admin_headers)
    assert res_admin_json.status_code == 200
    data = res_admin_json.json()
    assert len(data) == 1
    assert data[0]["rejected"] == "원본 답변: 내 이름은 [NAME]이고 메일은 [EMAIL]입니다."

    # 8. Test API access (Successful for admin - format: jsonl)
    res_admin_jsonl = await async_client.get("/api/v1/dpo/export?format=jsonl", headers=admin_headers)
    assert res_admin_jsonl.status_code == 200
    assert res_admin_jsonl.headers["content-type"] == "application/x-jsonlines"
    assert "attachment; filename=dpo_dataset.jsonl" in res_admin_jsonl.headers["content-disposition"]
    
    lines = res_admin_jsonl.text.strip().split("\n")
    assert len(lines) == 1
    import json
    parsed = json.loads(lines[0])
    assert parsed["rejected"] == "원본 답변: 내 이름은 [NAME]이고 메일은 [EMAIL]입니다."
