"""运行反馈（PostgreSQL 会话库，规划阶段 4.3）。

两类来源共用一张表：
- user_rating：用户对助手回答的 👍/👎（rating=1/-1，可带评论）。
- teacher_correction：教师改分时自动采集的与 AI 评分差值。
(run_id, user_id, source) 唯一——重复反馈按 upsert 覆盖。
"""
from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from ..assistant_database import AssistantBase
from .base import ModelMixin, TimestampMixin


class AgentFeedback(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_feedback"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "user_id", "source",
            name="uq_agent_feedback_run_user_source",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    source = Column(String(32), nullable=False)  # user_rating | teacher_correction
    rating = Column(Integer, nullable=True)  # 1 / -1（user_rating）
    comment = Column(Text, nullable=True)
    # teacher_correction：原始分制的 AI 分、教师分与差值
    ai_score = Column(Float, nullable=True)
    teacher_score = Column(Float, nullable=True)
    score_delta = Column(Float, nullable=True)
