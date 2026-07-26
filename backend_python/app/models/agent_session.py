from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentSession(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    actor_role = Column(String(20), nullable=False)
    title = Column(String(255), default="新会话")
    summary = Column(Text, default="")
    status = Column(String(20), default="active", nullable=False)
    runs = relationship("AgentRun", back_populates="session", cascade="all, delete-orphan")
