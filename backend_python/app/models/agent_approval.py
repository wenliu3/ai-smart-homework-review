from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentApproval(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_approvals"

    id = Column(String(64), primary_key=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requester_user_id = Column(Integer, nullable=False, index=True)
    requester_role = Column(String(20), nullable=False)
    approver_user_id = Column(Integer, nullable=True)
    action_type = Column(String(64), nullable=False)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(128), nullable=True)
    payload_json = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)
    summary = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    expires_at = Column(DateTime, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True)
    error_code = Column(String(64), nullable=True)
