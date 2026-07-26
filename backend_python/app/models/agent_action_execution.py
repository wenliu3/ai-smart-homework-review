"""MySQL 侧审批动作幂等账本，阻止跨库崩溃后的重复业务写入。"""
from sqlalchemy import Column, JSON, String

from ..database import Base
from .base import ModelMixin, TimestampMixin


class AgentActionExecution(Base, TimestampMixin, ModelMixin):
    __tablename__ = "agent_action_executions"

    idempotency_key = Column(String(64), primary_key=True)
    action_type = Column(String(64), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="executing", index=True)
    result_json = Column(JSON, nullable=True)
    error_code = Column(String(64), nullable=True)
