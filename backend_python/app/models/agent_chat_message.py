"""AI 助手聊天消息（存储于 PostgreSQL 会话库，与 MySQL 业务库物理隔离）"""
from sqlalchemy import Column, Integer, String, Text
from ..assistant_database import AssistantBase
from .base import TimestampMixin, ModelMixin


class AgentChatMessage(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 逻辑关联 users.id（跨库不加物理外键，由应用层保证归属校验）
    teacher_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
