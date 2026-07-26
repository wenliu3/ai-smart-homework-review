from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentRun(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_runs"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    intent = Column(String(50), nullable=False)
    risk_level = Column(String(20), default="low", nullable=False)
    graph_version = Column(String(32), default="teacher-v1", nullable=False)
    status = Column(String(20), default="running", nullable=False, index=True)
    final_output = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    usage_json = Column(JSON, default=dict)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    session = relationship("AgentSession", back_populates="runs")
    steps = relationship("AgentStep", back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.sequence")
    artifacts = relationship("AgentArtifact", back_populates="run", cascade="all, delete-orphan")
