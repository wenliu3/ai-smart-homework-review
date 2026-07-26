"""会话删除/改名与审批过期治理（规划阶段 4.4）。"""
from datetime import datetime, timedelta

import pytest

from app.agent.tools.approval import create_action_draft
from app.crud.agent_approval import create_approval, list_owned_approvals
from app.crud.agent_session import create_session
from app.models import AgentSession


@pytest.fixture()
def own_session(assistant_db, teacher):
    return create_session(
        assistant_db,
        user_id=teacher.id,
        actor_role="teacher",
        title="旧标题",
    )


# ========== 会话删除 ==========

def test_owner_can_archive_session(client, teacher, auth_header, own_session):
    response = client.delete(
        f"/api/assistant/sessions/{own_session.id}",
        headers=auth_header(teacher),
    )

    assert response.status_code == 200
    listed = client.get(
        "/api/assistant/sessions", headers=auth_header(teacher),
    )
    assert listed.json()["data"]["sessions"] == []


def test_cross_user_delete_returns_404(
    client, teacher, user_factory, auth_header, own_session,
):
    other = user_factory("t_sess_other", "teacher")

    response = client.delete(
        f"/api/assistant/sessions/{own_session.id}",
        headers=auth_header(other),
    )

    assert response.status_code == 404


def test_system_sessions_cannot_be_deleted(
    client, assistant_db, teacher, auth_header,
):
    create_session(
        assistant_db,
        user_id=teacher.id,
        actor_role="teacher",
        session_id="grading-protected0001",
        title="批改任务",
    )

    response = client.delete(
        "/api/assistant/sessions/grading-protected0001",
        headers=auth_header(teacher),
    )

    assert response.status_code == 400


# ========== 会话改名 ==========

def test_owner_can_rename_session(
    client, assistant_db, teacher, auth_header, own_session,
):
    response = client.patch(
        f"/api/assistant/sessions/{own_session.id}",
        headers=auth_header(teacher),
        json={"title": "微积分答疑"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "微积分答疑"
    assistant_db.expire_all()
    assert assistant_db.query(AgentSession).filter(
        AgentSession.id == own_session.id,
    ).one().title == "微积分答疑"


def test_rename_rejects_blank_title(
    client, teacher, auth_header, own_session,
):
    response = client.patch(
        f"/api/assistant/sessions/{own_session.id}",
        headers=auth_header(teacher),
        json={"title": "   "},
    )

    assert response.status_code in (400, 422)


def test_cross_user_rename_returns_404(
    client, user_factory, auth_header, own_session,
):
    other = user_factory("t_rename_other", "teacher")

    response = client.patch(
        f"/api/assistant/sessions/{own_session.id}",
        headers=auth_header(other),
        json={"title": "越权改名"},
    )

    assert response.status_code == 404


# ========== 审批过期治理 ==========

def _draft(seed: str):
    return create_action_draft(
        action_type="create_ai_rule",
        target_type="ai_rule",
        target_id=None,
        parameters={"name": f"规则-{seed}", "prompt": "按量表批改"},
        summary=f"创建规则 {seed}",
        risk_level="medium",
        ttl_seconds=600,
        idempotency_seed=seed,
    )


def test_expired_pending_drafts_leave_pending_list(assistant_db, teacher):
    fresh = create_approval(
        assistant_db,
        draft=_draft("fresh"),
        requester_user_id=teacher.id,
        requester_role="teacher",
    )
    stale = create_approval(
        assistant_db,
        draft=_draft("stale"),
        requester_user_id=teacher.id,
        requester_role="teacher",
    )
    stale.expires_at = datetime.now() - timedelta(minutes=5)
    assistant_db.commit()

    pending = list_owned_approvals(
        assistant_db, user_id=teacher.id, status="pending",
    )

    assert [item.id for item in pending] == [fresh.id]
    # 过期草案被标记为 expired（历史标签可见），而不是永久停在 pending
    assistant_db.expire_all()
    assert stale.status == "expired"


def test_expiry_sweep_only_touches_own_pending_rows(
    assistant_db, teacher, user_factory,
):
    other = user_factory("t_expire_other", "teacher")
    others_stale = create_approval(
        assistant_db,
        draft=_draft("other"),
        requester_user_id=other.id,
        requester_role="teacher",
    )
    others_stale.expires_at = datetime.now() - timedelta(minutes=5)
    assistant_db.commit()

    list_owned_approvals(assistant_db, user_id=teacher.id, status="pending")

    assistant_db.expire_all()
    # 别人的过期草案不动，等其本人查询时再惰性标记
    assert others_stale.status == "pending"


# ========== 运行明细 steps 摘要（规划 4.4） ==========

def test_run_detail_includes_step_summaries(
    client, assistant_db, teacher, auth_header,
):
    from app.crud import agent_run

    session = create_session(
        assistant_db, user_id=teacher.id, actor_role="teacher",
    )
    run = agent_run.create_run(
        assistant_db, session_id=session.id, user_id=teacher.id, intent="pending",
    )
    agent_run.append_step(
        assistant_db, run.id, teacher.id,
        node_name="teacher_supervisor", status="completed", duration_ms=12,
    )
    agent_run.append_step(
        assistant_db, run.id, teacher.id,
        node_name="teacher_data_agent", status="failed",
        error_code="AGENT_CHAT_ERROR", duration_ms=880,
    )

    response = client.get(
        f"/api/assistant/runs/{run.id}", headers=auth_header(teacher),
    )

    assert response.status_code == 200
    steps = response.json()["data"]["steps"]
    assert [step["nodeName"] for step in steps] == [
        "teacher_supervisor", "teacher_data_agent",
    ]
    assert steps[0] == {
        "nodeName": "teacher_supervisor",
        "status": "completed",
        "durationMs": 12,
        "errorCode": None,
    }
    assert steps[1]["errorCode"] == "AGENT_CHAT_ERROR"
    # 摘要不包含 output/证据正文，避免泄露节点内部细节
    assert "output" not in steps[0]
    assert "outputJson" not in steps[0]


# ========== 会话摘要写回（规划 4.4） ==========

def test_teacher_finalize_writes_session_summary(assistant_db):
    from app.agent.service import orchestrate_teacher_run
    from tests.integration.agent.test_run_usage_persistence import (
        _UsageSpecialists,
    )

    session = create_session(
        assistant_db, user_id=7, actor_role="teacher", session_id="sesssumm0001",
    )

    orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-summ-001",
        specialists=_UsageSpecialists(),
        assistant_db=assistant_db,
    )

    assistant_db.expire_all()
    row = assistant_db.query(AgentSession).filter(
        AgentSession.id == session.id,
    ).one()
    assert row.summary
    assert "我有几个班级" in row.summary
    assert len(row.summary) <= 500


def test_summary_failure_does_not_break_run(assistant_db, monkeypatch):
    from app.agent import service as service_module
    from tests.integration.agent.test_run_usage_persistence import (
        _UsageSpecialists,
    )

    monkeypatch.setattr(
        service_module.agent_session_crud,
        "update_summary",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("PG down")),
    )
    session = create_session(
        assistant_db, user_id=7, actor_role="teacher", session_id="sesssumm0002",
    )

    result = service_module.orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-summ-002",
        specialists=_UsageSpecialists(),
        assistant_db=assistant_db,
    )

    assert result.status == "completed"
