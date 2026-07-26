"""会话库（PostgreSQL，测试用 SQLite 替身）接入测试。

验证双库边界：AgentChatMessage 归属 AssistantBase、无跨库外键、
可读写、应用启动时自动建表。
"""
from sqlalchemy import inspect

from app.assistant_database import AssistantBase, assistant_engine
from app.database import Base
from app.models import AgentChatMessage


def test_agent_chat_message_belongs_to_assistant_base():
    assert "agent_chat_messages" in AssistantBase.metadata.tables
    assert "agent_chat_messages" not in Base.metadata.tables


def test_agent_chat_message_has_no_cross_db_foreign_key():
    table = AssistantBase.metadata.tables["agent_chat_messages"]
    assert list(table.c.teacher_id.foreign_keys) == []
    # teacher_id 保留索引（按教师查会话是高频条件）
    assert any(ix.columns.get("teacher_id") is not None for ix in table.indexes)


def test_insert_and_read_message(assistant_db):
    assistant_db.add(AgentChatMessage(teacher_id=1, session_id="s1", role="user", content="你好"))
    assistant_db.commit()
    rows = assistant_db.query(AgentChatMessage).filter_by(session_id="s1").all()
    assert len(rows) == 1
    assert rows[0].content == "你好"


def test_startup_creates_assistant_tables(client):
    insp = inspect(assistant_engine)
    assert "agent_chat_messages" in insp.get_table_names()
