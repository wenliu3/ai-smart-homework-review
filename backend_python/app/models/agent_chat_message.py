"""Agent 聊天消息记录模型"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from ..database import Base
from .base import TimestampMixin, ModelMixin


class AgentChatMessage(Base, TimestampMixin, ModelMixin):
    __tablename__ = "agent_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)