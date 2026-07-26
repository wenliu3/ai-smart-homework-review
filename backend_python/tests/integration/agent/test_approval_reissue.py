"""审批幂等重发测试：终态（rejected/expired/failed）记录不应永久占用幂等键。

覆盖：
- rejected 后同载荷可重新发起审批（旧记录归档保留审计）。
- expired（含 pending 但已过 expires_at）后可重新发起。
- failed 后可重新发起。
- pending 未过期时保持幂等返回原记录（回归）。
- 「先查后插」并发竞态撞唯一约束时不 500，返回已存在记录。
"""
from datetime import datetime, timedelta

from app.agent.tools.approval import create_action_draft
from app.crud import agent_approval as approval_crud
from app.models import AgentApproval

APPROVALS_URL = "/api/assistant/approvals"

_RULE_PAYLOAD = {
    "actionType": "create_ai_rule",
    "targetType": "ai_rule",
    "parameters": {
        "name": "重发测试规则",
        "modelType": "deepseek",
        "prompt": "按评分量表逐项评价",
    },
    "summary": "创建一条 AI 评分规则草案",
    "riskLevel": "medium",
}


def _create_via_api(client, headers):
    resp = client.post(APPROVALS_URL, headers=headers, json=_RULE_PAYLOAD)
    assert resp.status_code == 200
    return resp.json()["data"]


def test_pending_approval_stays_idempotent(client, teacher, auth_header):
    """回归：pending 未过期时同载荷返回同一条记录。"""
    headers = auth_header(teacher)
    first = _create_via_api(client, headers)
    second = _create_via_api(client, headers)
    assert second["approvalId"] == first["approvalId"]
    assert second["status"] == "pending"


def test_rejected_approval_can_be_reissued(client, teacher, auth_header, assistant_db):
    headers = auth_header(teacher)
    first = _create_via_api(client, headers)
    rejected = client.post(
        f"{APPROVALS_URL}/{first['approvalId']}/reject",
        headers=headers,
        json={"reason": "本次不执行"},
    )
    assert rejected.status_code == 200

    second = _create_via_api(client, headers)

    assert second["approvalId"] != first["approvalId"]
    assert second["status"] == "pending"
    # 旧记录保留审计，幂等键被归档为不冲突值
    assistant_db.expire_all()
    old = assistant_db.query(AgentApproval).filter(
        AgentApproval.id == first["approvalId"],
    ).one()
    assert old.status == "rejected"
    assert ":superseded:" in old.idempotency_key


def test_expired_pending_approval_can_be_reissued(client, teacher, auth_header, assistant_db):
    headers = auth_header(teacher)
    first = _create_via_api(client, headers)
    assistant_db.query(AgentApproval).filter(
        AgentApproval.id == first["approvalId"],
    ).update({AgentApproval.expires_at: datetime.now() - timedelta(minutes=1)})
    assistant_db.commit()

    second = _create_via_api(client, headers)

    assert second["approvalId"] != first["approvalId"]
    assert second["status"] == "pending"
    assistant_db.expire_all()
    old = assistant_db.query(AgentApproval).filter(
        AgentApproval.id == first["approvalId"],
    ).one()
    assert old.status == "expired"
    assert ":superseded:" in old.idempotency_key


def test_failed_approval_can_be_reissued(client, teacher, auth_header, assistant_db):
    headers = auth_header(teacher)
    first = _create_via_api(client, headers)
    assistant_db.query(AgentApproval).filter(
        AgentApproval.id == first["approvalId"],
    ).update({AgentApproval.status: "failed"})
    assistant_db.commit()

    second = _create_via_api(client, headers)

    assert second["approvalId"] != first["approvalId"]
    assert second["status"] == "pending"


def test_concurrent_create_returns_existing_without_error(
    assistant_db, teacher, monkeypatch,
):
    """模拟「先查后插」竞态：存在性检查未命中但插入撞唯一约束，应返回已存在记录。"""
    draft = create_action_draft(
        action_type="create_ai_rule",
        target_type="ai_rule",
        target_id=None,
        parameters={"name": "并发规则", "modelType": "deepseek", "prompt": "p"},
        summary="并发竞态测试",
        risk_level="medium",
        idempotency_seed=f"teacher:{teacher.id}:manual",
    )
    first = approval_crud.create_approval(
        assistant_db,
        draft=draft,
        requester_user_id=teacher.id,
        requester_role="teacher",
    )

    real_lookup = approval_crud._get_by_idempotency_key
    calls = {"n": 0}

    def _racy_lookup(db, key):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # 第一次检查时假装不存在（并发方尚未提交）
        return real_lookup(db, key)

    monkeypatch.setattr(approval_crud, "_get_by_idempotency_key", _racy_lookup)
    second = approval_crud.create_approval(
        assistant_db,
        draft=draft,
        requester_user_id=teacher.id,
        requester_role="teacher",
    )

    assert second.id == first.id
    assert calls["n"] >= 2
