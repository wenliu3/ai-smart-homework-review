from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentMessage(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String(64), nullable=True, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), default="markdown", nullable=False)
    metadata_json = Column(JSON, default=dict)
