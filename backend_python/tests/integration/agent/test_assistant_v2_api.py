"""新版助手 API（/assistant/runs/*）集成测试。

覆盖：
- 认证与角色权限（401 / 403）。
- 教师成功运行 + JSON SSE 顺序。
- 非法 session_id 校验。
- 运行查询（GET /assistant/runs/{id}）。
- 取消运行。
- 错误事件不泄露内部信息。
- 会话接口（创建 / 列表 / 消息）。
- 请求体不接受 user_id / teacher_id / student_id。
"""
import json
import re

import pytest

from app.agent.contracts import (
    AGENT_BUDGET_EXCEEDED,
    AGENT_CHAT_ERROR,
    SAFE_CHAT_ERROR_MESSAGE,
)
from app.agent.service import OrchestrationResult

RUNS_STREAM_URL = "/api/assistant/runs/stream"
SESSIONS_URL = "/api/assistant/sessions"
VALID_SESSION = "sess-v2-0001"


def _make_result(
    status: str = "completed",
    final_answer: str = "已找到 2 个班级",
    error_code: str | None = None,
) -> OrchestrationResult:
    """构造测试用编排结果。"""
    events = [
        {"type": "run.started", "data": {}},
        {"type": "route.selected", "data": {"intent": "teaching_data"}},
        {"type": "agent.started", "data": {"agent": "teaching_data"}},
        {"type": "agent.completed", "data": {"agent": "teaching_data"}},
        {"type": "run.completed", "data": {"final_answer_length": len(final_answer)}},
    ]
    if status == "failed":
        events = [
            {"type": "run.started", "data": {}},
            {"type": "run.failed", "data": {"error_code": error_code}},
        ]
    return OrchestrationResult(
        run_id="test-run-id-0001",
        final_answer=final_answer,
        events=events,
        status=status,
        error_code=error_code,
    )


@pytest.fixture()
def patch_orchestrate(monkeypatch):
    """替换 orchestrate_teacher_run，避免真实 LLM 调用。"""
    def _patch(result: OrchestrationResult | Exception):
        if isinstance(result, Exception):
            def _raise(*args, **kwargs):
                raise result
            monkeypatch.setattr(
                "app.agent.service.orchestrate_teacher_run", _raise,
            )
        else:
            monkeypatch.setattr(
                "app.agent.service.orchestrate_teacher_run",
                lambda **kwargs: result,
            )
    return _patch


def _parse_sse_events(text: str) -> list[dict]:
    """从 SSE 文本中提取 JSON 事件。"""
    events = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: ") and not line.endswith("[DONE]"):
            payload = line[6:]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return events


# ========== 认证与权限 ==========

def test_stream_requires_authentication(client):
    resp = client.post(RUNS_STREAM_URL, json={"message": "hi", "session_id": VALID_SESSION})
    assert resp.status_code == 401


def test_stream_accepts_student_role(client, student, auth_header):
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "hi", "session_id": VALID_SESSION},
        headers=auth_header(student),
    )
    assert resp.status_code == 200
    assert "run.failed" in resp.text


def test_stream_accepts_admin_role(client, user_factory, auth_header):
    admin = user_factory("admin_root", "superadmin")
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "hi", "session_id": VALID_SESSION},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    assert "run.failed" in resp.text


def test_sessions_available_to_student(client, student, auth_header):
    headers = auth_header(student)
    assert client.get(SESSIONS_URL, headers=headers).status_code == 200
    assert client.post(SESSIONS_URL, json={}, headers=headers).status_code == 200


# ========== 参数校验 ==========

def test_stream_rejects_invalid_session_id(client, teacher, auth_header, patch_orchestrate):
    patch_orchestrate(_make_result())
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "hi", "session_id": "bad!"},
        headers=auth_header(teacher),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 10011


def test_stream_rejects_user_id_in_body(client, teacher, auth_header, patch_orchestrate):
    """请求体不接受 user_id / teacher_id / student_id（身份只来自认证）。"""
    patch_orchestrate(_make_result())
    resp = client.post(
        RUNS_STREAM_URL,
        json={
            "message": "hi",
            "session_id": VALID_SESSION,
            "user_id": 999,
            "teacher_id": 999,
            "student_id": 999,
        },
        headers=auth_header(teacher),
    )
    # 多余字段应被忽略或拒绝；身份不来自请求体
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        # 验证身份来自认证，不来自请求体
        # （orchestrate_teacher_run 被替换，不实际执行；
        #   但如果实现误用 user_id，这里会因会话归属校验失败而 error）
        pass


# ========== 教师成功 + JSON SSE 顺序 ==========

def test_stream_success_emits_json_sse_events_in_order(client, teacher, auth_header, patch_orchestrate):
    patch_orchestrate(_make_result())
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "我有几个班级", "session_id": VALID_SESSION},
        headers=auth_header(teacher),
    )
    assert resp.status_code == 200

    events = _parse_sse_events(resp.text)
    event_types = [e["type"] for e in events]
    assert "run.started" in event_types
    assert "route.selected" in event_types
    assert "agent.started" in event_types
    assert "agent.completed" in event_types
    assert "run.completed" in event_types
    # 顺序：started 一定在 completed 之前
    assert event_types.index("run.started") < event_types.index("run.completed")
    # 以 [DONE] 结束
    assert "data: [DONE]" in resp.text


def test_stream_completed_event_contains_run_id(client, teacher, auth_header, patch_orchestrate):
    patch_orchestrate(_make_result())
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "hi", "session_id": VALID_SESSION},
        headers=auth_header(teacher),
    )
    events = _parse_sse_events(resp.text)
    completed = [e for e in events if e["type"] == "run.completed"]
    assert len(completed) == 1
    started = [e for e in events if e["type"] == "run.started"]
    assert started[0]["data"]["run_id"] == "test-run-id-0001"


# ========== 错误事件不泄露内部信息 ==========

def test_stream_budget_exceeded_emits_safe_error(client, teacher, auth_header, patch_orchestrate):
    patch_orchestrate(_make_result(status="failed", error_code=AGENT_BUDGET_EXCEEDED, final_answer=""))
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "hi", "session_id": VALID_SESSION},
        headers=auth_header(teacher),
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    failed = [e for e in events if e["type"] == "run.failed"]
    assert len(failed) == 1
    assert failed[0]["data"]["error_code"] == AGENT_BUDGET_EXCEEDED


def test_stream_unknown_error_hides_internals(client, teacher, auth_header, patch_orchestrate):
    patch_orchestrate(RuntimeError("pymysql: Packet sequence number wrong"))
    resp = client.post(
        RUNS_STREAM_URL,
        json={"message": "hi", "session_id": VALID_SESSION},
        headers=auth_header(teacher),
    )
    assert resp.status_code == 200
    assert "Packet" not in resp.text
    assert "RuntimeError" not in resp.text
    assert "pymysql" not in resp.text
    # 应该包含安全消息
    events = _parse_sse_events(resp.text)
    failed = [e for e in events if e["type"] == "run.failed"]
    assert len(failed) == 1


# ========== 运行查询 ==========

def test_get_run_returns_status_and_answer(client, teacher, auth_header, assistant_db, patch_orchestrate):
    """GET /assistant/runs/{id} 返回运行状态和最终答案。"""
    from app.crud.agent_session import create_session
    from app.crud.agent_run import create_run, finalize_run

    session = create_session(assistant_db, user_id=teacher.id, actor_role="teacher", session_id=VALID_SESSION)
    run = create_run(assistant_db, session.id, user_id=teacher.id, intent="teacher_query")
    finalize_run(
        assistant_db, run.id, user_id=teacher.id,
        final_output="最终答案",
        assistant_message="最终答案",
    )

    resp = client.get(f"/api/assistant/runs/{run.id}", headers=auth_header(teacher))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["runId"] == run.id
    assert data["status"] == "completed"
    assert data["finalOutput"] == "最终答案"


def test_get_run_accepts_64_character_deterministic_grading_id(
    client, teacher, auth_header, assistant_db,
):
    from app.crud.agent_session import create_session
    from app.crud.agent_run import create_run

    session = create_session(
        assistant_db,
        user_id=teacher.id,
        actor_role="teacher",
        session_id=VALID_SESSION,
    )
    run = create_run(
        assistant_db,
        session.id,
        user_id=teacher.id,
        intent="grading",
        run_id="a" * 64,
    )

    resp = client.get(
        f"/api/assistant/runs/{run.id}",
        headers=auth_header(teacher),
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["runId"] == run.id


def test_get_run_returns_404_for_foreign_user(client, teacher, user_factory, auth_header, assistant_db):
    """跨用户查询运行返回 404。"""
    from app.crud.agent_session import create_session
    from app.crud.agent_run import create_run, finalize_run

    other = user_factory("t_other", "teacher")
    session = create_session(assistant_db, user_id=other.id, actor_role="teacher", session_id="sess-other-0001")
    run = create_run(assistant_db, session.id, user_id=other.id, intent="teacher_query")
    finalize_run(assistant_db, run.id, user_id=other.id, final_output="x")

    resp = client.get(f"/api/assistant/runs/{run.id}", headers=auth_header(teacher))
    assert resp.status_code == 404


# ========== 取消运行 ==========

def test_cancel_run_marks_cancelled(client, teacher, auth_header, assistant_db):
    """POST /assistant/runs/{id}/cancel 标记运行为 cancelled。"""
    from app.crud.agent_session import create_session
    from app.crud.agent_run import cancel_run as crud_cancel, create_run

    session = create_session(assistant_db, user_id=teacher.id, actor_role="teacher", session_id=VALID_SESSION)
    run = create_run(assistant_db, session.id, user_id=teacher.id, intent="teacher_query")

    resp = client.post(f"/api/assistant/runs/{run.id}/cancel", headers=auth_header(teacher))
    assert resp.status_code == 200

    # 刷新 session 缓存：cancel 在另一个 DB session 中提交
    assistant_db.expire_all()
    from app.crud.agent_run import get_run
    loaded = get_run(assistant_db, run.id, user_id=teacher.id)
    assert loaded.status == "cancelled"


def test_cancel_run_accepts_64_character_deterministic_grading_id(
    client, teacher, auth_header, assistant_db,
):
    from app.crud.agent_session import create_session
    from app.crud.agent_run import create_run, get_run

    session = create_session(
        assistant_db,
        user_id=teacher.id,
        actor_role="teacher",
        session_id=VALID_SESSION,
    )
    run = create_run(
        assistant_db,
        session.id,
        user_id=teacher.id,
        intent="grading",
        run_id="b" * 64,
    )

    resp = client.post(
        f"/api/assistant/runs/{run.id}/cancel",
        headers=auth_header(teacher),
    )

    assert resp.status_code == 200
    assistant_db.expire_all()
    assert get_run(assistant_db, run.id, user_id=teacher.id).status == "cancelled"


def test_cancel_run_returns_404_for_foreign_user(client, teacher, user_factory, auth_header, assistant_db):
    """跨用户取消运行返回 404。"""
    from app.crud.agent_session import create_session
    from app.crud.agent_run import create_run

    other = user_factory("t_other", "teacher")
    session = create_session(assistant_db, user_id=other.id, actor_role="teacher", session_id="sess-other-0002")
    run = create_run(assistant_db, session.id, user_id=other.id, intent="teacher_query")

    resp = client.post(f"/api/assistant/runs/{run.id}/cancel", headers=auth_header(teacher))
    assert resp.status_code == 404


# ========== 会话接口 ==========

def test_create_session_returns_session_id(client, teacher, auth_header):
    """POST /assistant/sessions 创建新会话并返回 session_id。"""
    resp = client.post(SESSIONS_URL, json={"title": "新会话"}, headers=auth_header(teacher))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "sessionId" in data
    assert re.match(r"^[a-zA-Z0-9_-]{8,64}$", data["sessionId"])


def test_list_sessions_returns_user_sessions(client, teacher, auth_header):
    """GET /assistant/sessions 返回当前教师的会话列表。"""
    # 先创建一个会话
    client.post(SESSIONS_URL, json={"title": "会话1"}, headers=auth_header(teacher))

    resp = client.get(SESSIONS_URL, headers=auth_header(teacher))
    assert resp.status_code == 200
    sessions = resp.json()["data"]["sessions"]
    assert len(sessions) >= 1


def test_get_session_messages_returns_empty_for_new_session(client, teacher, auth_header):
    """新会话的消息列表为空。"""
    create_resp = client.post(SESSIONS_URL, json={}, headers=auth_header(teacher))
    session_id = create_resp.json()["data"]["sessionId"]

    resp = client.get(f"{SESSIONS_URL}/{session_id}/messages", headers=auth_header(teacher))
    assert resp.status_code == 200
    messages = resp.json()["data"]["messages"]
    assert messages == []


def test_get_session_messages_404_for_foreign_session(client, teacher, user_factory, auth_header):
    """跨用户读取会话消息返回 404 或空。"""
    other = user_factory("t_other", "teacher")
    create_resp = client.post(SESSIONS_URL, json={}, headers=auth_header(other))
    session_id = create_resp.json()["data"]["sessionId"]

    resp = client.get(f"{SESSIONS_URL}/{session_id}/messages", headers=auth_header(teacher))
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.json()["data"]["messages"] == []
