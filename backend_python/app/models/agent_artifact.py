from sqlalchemy import JSON, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentArtifact(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(String(64), nullable=False)
    schema_version = Column(String(32), nullable=False)
    payload_json = Column(JSON, nullable=False)
    run = relationship("AgentRun", back_populates="artifacts")
