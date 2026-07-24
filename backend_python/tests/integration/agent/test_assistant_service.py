"""对话编排服务测试：事件序列、落库时机、错误安全、兜底存储。"""
import pytest
from langchain_core.messages import AIMessageChunk

from app.agent.service import ChatStreamEvent, stream_chat_events
from app.core.exceptions import BizException
from app.crud import agent_chat as crud
from app.models import AgentChatMessage
from tests.fakes import FakeAgent


@pytest.fixture()
def patch_agent(monkeypatch):
    def _patch(agent):
        monkeypatch.setattr("app.agent.service._get_agent", lambda db: agent)
    return _patch


def _roles_of_saved(assistant_db, teacher_id, session_id):
    rows = (
        assistant_db.query(AgentChatMessage)
        .filter_by(teacher_id=teacher_id, session_id=session_id)
        .order_by(AgentChatMessage.id)
        .all()
    )
    return [(r.role, r.content) for r in rows]


def test_stream_success_emits_chunks_then_done_and_saves(assistant_db, teacher, patch_agent):
    patch_agent(FakeAgent(["数据如下", "：3 个班级"]))
    events = list(stream_chat_events(teacher.id, "我有几个班级", "sess0001"))
    assert [e.data for e in events if e.event is None] == ["数据如下", "：3 个班级"]
    assert events[-1] == ChatStreamEvent(event="done", data="[DONE]")
    assert _roles_of_saved(assistant_db, teacher.id, "sess0001") == [
        ("user", "我有几个班级"),
        ("assistant", "数据如下：3 个班级"),
    ]


def test_history_loaded_into_agent_input(assistant_db, teacher, patch_agent):
    crud.save_exchange(assistant_db, teacher.id, "sess0002", "之前的问题", "之前的回答")
    agent = FakeAgent(["好的"])
    patch_agent(agent)
    list(stream_chat_events(teacher.id, "新问题", "sess0002"))
    messages = agent.received_input["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "之前的问题"),
        ("assistant", "之前的回答"),
        ("user", "新问题"),
    ]


def test_biz_exception_passes_safe_message(assistant_db, teacher, monkeypatch):
    def _raise(db_):
        raise BizException(10016, "数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")
    monkeypatch.setattr("app.agent.service._get_agent", _raise)
    events = list(stream_chat_events(teacher.id, "hi", "sess0003"))
    assert events == [ChatStreamEvent(event="error", data="数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")]
    assert assistant_db.query(AgentChatMessage).count() == 0


def test_unknown_error_hides_internals(assistant_db, teacher, patch_agent):
    patch_agent(FakeAgent(error=RuntimeError("pymysql: Packet sequence number wrong")))
    events = list(stream_chat_events(teacher.id, "hi", "sess0004"))
    errors = [e for e in events if e.event == "error"]
    assert len(errors) == 1
    assert errors[0].data == "AI 服务暂时不可用，请稍后重试"
    assert "Packet" not in errors[0].data
    assert "RuntimeError" not in errors[0].data


def test_partial_answer_saved_when_stream_breaks(assistant_db, teacher, patch_agent):
    class BrokenAgent:
        def stream(self, input, context=None, stream_mode=None):
            yield (AIMessageChunk(content="半截回答"), {})
            raise ConnectionError("reset by peer")

    patch_agent(BrokenAgent())
    events = list(stream_chat_events(teacher.id, "hi", "sess0005"))
    assert [e.data for e in events if e.event is None] == ["半截回答"]
    assert any(e.event == "error" for e in events)
    assert _roles_of_saved(assistant_db, teacher.id, "sess0005") == [
        ("user", "hi"),
        ("assistant", "半截回答"),
    ]
