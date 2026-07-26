from sqlalchemy import JSON, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentStep(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    node_name = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False)
    output_json = Column(JSON, default=dict)
    evidence_refs = Column(JSON, default=list)
    usage_json = Column(JSON, default=dict)
    error_code = Column(String(64), nullable=True)
    duration_ms = Column(Integer, default=0)
    run = relationship("AgentRun", back_populates="steps")
