"""教师助手 API 集成测试：角色权限、SSE 旧格式兼容、错误安全、会话隔离。"""
import pytest

from app.models import AgentChatMessage
from tests.fakes import FakeAgent

CHAT_URL = "/api/teacher/assistant/chat/stream"
SESSIONS_URL = "/api/teacher/assistant/sessions"
VALID_SESSION = "sess0001"


@pytest.fixture()
def patch_agent(monkeypatch):
    def _patch(agent):
        monkeypatch.setattr("app.agent.service._get_agent", lambda db: agent)
    return _patch


# ---------- 权限 ----------

def test_chat_requires_authentication(client):
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION})
    assert resp.status_code == 401


def test_chat_forbidden_for_student(client, student, auth_header):
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION}, headers=auth_header(student))
    assert resp.status_code == 403
    assert resp.json()["code"] == 10007


def test_chat_forbidden_for_admin(client, user_factory, auth_header):
    admin = user_factory("admin_root", "superadmin")
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION}, headers=auth_header(admin))
    assert resp.status_code == 403


def test_session_apis_forbidden_for_student(client, student, auth_header):
    headers = auth_header(student)
    assert client.get(SESSIONS_URL, headers=headers).status_code == 403
    assert client.get(f"{SESSIONS_URL}/s1/messages", headers=headers).status_code == 403
    assert client.delete(f"{SESSIONS_URL}/all", headers=headers).status_code == 403
    assert client.delete(f"{SESSIONS_URL}/s1", headers=headers).status_code == 403


# ---------- 参数校验 ----------

def test_chat_rejects_invalid_session_id(client, teacher, auth_header):
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": "bad!"}, headers=auth_header(teacher))
    assert resp.status_code == 400
    assert resp.json()["code"] == 10011


# ---------- SSE 旧格式兼容 ----------

def test_chat_stream_success_legacy_format(client, teacher, assistant_db, auth_header, patch_agent):
    patch_agent(FakeAgent(["你好", "，老师"]))
    resp = client.post(CHAT_URL, json={"message": "我有几个班级", "session_id": VALID_SESSION}, headers=auth_header(teacher))
    assert resp.status_code == 200
    assert "data: 你好" in resp.text
    assert "event: done" in resp.text
    assert "event: message" not in resp.text  # 旧格式：正文分片不带 event 字段
    rows = assistant_db.query(AgentChatMessage).filter_by(teacher_id=teacher.id, session_id=VALID_SESSION).all()
    assert len(rows) == 2


def test_chat_error_event_hides_internals(client, teacher, auth_header, patch_agent):
    patch_agent(FakeAgent(error=RuntimeError("pymysql: Packet sequence number wrong")))
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION}, headers=auth_header(teacher))
    assert "event: error" in resp.text
    assert "Packet sequence" not in resp.text
    assert "RuntimeError" not in resp.text


# ---------- 会话接口 ----------

def test_session_lifecycle(client, teacher, auth_header, patch_agent):
    patch_agent(FakeAgent(["回答内容"]))
    headers = auth_header(teacher)
    client.post(CHAT_URL, json={"message": "问题一", "session_id": VALID_SESSION}, headers=headers)

    resp = client.get(SESSIONS_URL, headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()["data"]["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["sessionId"] == VALID_SESSION
    assert sessions[0]["messageCount"] == 2

    resp = client.get(f"{SESSIONS_URL}/{VALID_SESSION}/messages", headers=headers)
    assert [m["role"] for m in resp.json()["data"]["messages"]] == ["user", "assistant"]

    resp = client.delete(f"{SESSIONS_URL}/{VALID_SESSION}", headers=headers)
    assert resp.status_code == 200
    resp = client.get(SESSIONS_URL, headers=headers)
    assert resp.json()["data"]["sessions"] == []


def test_sessions_isolated_between_teachers(client, teacher, user_factory, auth_header, patch_agent):
    patch_agent(FakeAgent(["回答"]))
    client.post(CHAT_URL, json={"message": "问题", "session_id": VALID_SESSION}, headers=auth_header(teacher))
    other = user_factory("t_other", "teacher")
    resp = client.get(SESSIONS_URL, headers=auth_header(other))
    assert resp.json()["data"]["sessions"] == []
