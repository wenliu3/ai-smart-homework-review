"""会话消息 CRUD 测试：最近消息窗口、会话聚合、归属隔离、删除。"""
from datetime import datetime, timedelta

from app.crud import agent_chat as crud
from app.models import AgentChatMessage

BASE = datetime(2026, 7, 24, 10, 0, 0)


def _msg(assistant_db, teacher_id, session_id, role, content, seconds=0):
    """显式指定 created_at（server_default 为秒级精度，同秒排序不稳定）。"""
    m = AgentChatMessage(
        teacher_id=teacher_id, session_id=session_id,
        role=role, content=content,
        created_at=BASE + timedelta(seconds=seconds),
    )
    assistant_db.add(m)
    assistant_db.commit()
    return m


def test_get_recent_messages_chronological(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "user", "第一条", 1)
    _msg(assistant_db, teacher.id, "s1", "assistant", "第二条", 2)
    _msg(assistant_db, teacher.id, "s1", "user", "第三条", 3)
    history = crud.get_recent_messages(assistant_db, teacher.id, "s1", limit=10)
    assert [h["content"] for h in history] == ["第一条", "第二条", "第三条"]


def test_get_recent_messages_respects_limit(assistant_db, teacher):
    for i in range(12):
        _msg(assistant_db, teacher.id, "s1", "user", f"消息{i}", i)
    history = crud.get_recent_messages(assistant_db, teacher.id, "s1", limit=10)
    assert len(history) == 10
    assert history[0]["content"] == "消息2"
    assert history[-1]["content"] == "消息11"


def test_get_recent_messages_isolated_by_teacher_and_session(assistant_db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _msg(assistant_db, other.id, "s1", "user", "别的老师", 1)
    _msg(assistant_db, teacher.id, "s2", "user", "别的会话", 2)
    _msg(assistant_db, teacher.id, "s1", "user", "我的", 3)
    history = crud.get_recent_messages(assistant_db, teacher.id, "s1")
    assert [h["content"] for h in history] == ["我的"]


def test_save_exchange_writes_user_then_assistant(assistant_db, teacher):
    crud.save_exchange(assistant_db, teacher.id, "s2", "问题", "回答")
    rows = (
        assistant_db.query(AgentChatMessage)
        .filter_by(teacher_id=teacher.id, session_id="s2")
        .order_by(AgentChatMessage.id)
        .all()
    )
    assert [(r.role, r.content) for r in rows] == [("user", "问题"), ("assistant", "回答")]


def test_list_sessions_summary_and_order(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "user", "你好", 1)
    _msg(assistant_db, teacher.id, "s1", "assistant", "回答一", 2)
    _msg(assistant_db, teacher.id, "s2", "user", "另一个会话", 3)
    sessions = crud.list_sessions(assistant_db, teacher.id)
    assert [s["sessionId"] for s in sessions] == ["s2", "s1"]
    s1 = next(s for s in sessions if s["sessionId"] == "s1")
    assert s1["messageCount"] == 2
    assert s1["lastMessage"] == "回答一"
    assert s1["lastTime"] is not None


def test_list_sessions_truncates_long_last_message(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "assistant", "x" * 60, 1)
    sessions = crud.list_sessions(assistant_db, teacher.id)
    assert sessions[0]["lastMessage"] == "x" * 50 + "..."


def test_get_session_messages_chronological_with_camel_keys(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "user", "问", 2)
    _msg(assistant_db, teacher.id, "s1", "assistant", "答", 1)
    messages = crud.get_session_messages(assistant_db, teacher.id, "s1")
    assert [(m["role"], m["content"]) for m in messages] == [("assistant", "答"), ("user", "问")]
    assert set(messages[0].keys()) == {"role", "content", "createdAt"}


def test_delete_session_only_removes_own_session(assistant_db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _msg(assistant_db, teacher.id, "s1", "user", "我的", 1)
    _msg(assistant_db, other.id, "s1", "user", "别人的", 2)
    deleted = crud.delete_session(assistant_db, teacher.id, "s1")
    assert deleted == 1
    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=other.id).count() == 1


def test_delete_all_sessions_only_own(assistant_db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _msg(assistant_db, teacher.id, "s1", "user", "a", 1)
    _msg(assistant_db, teacher.id, "s2", "user", "b", 2)
    _msg(assistant_db, other.id, "s1", "user", "c", 3)
    deleted = crud.delete_all_sessions(assistant_db, teacher.id)
    assert deleted == 2
    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=other.id).count() == 1
