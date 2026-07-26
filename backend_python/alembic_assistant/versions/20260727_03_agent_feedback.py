"""agent feedback

运行反馈表（规划阶段 4.3）：用户 👍/👎 与教师改分差值自动采集。

Revision ID: 20260727_03
Revises: 20260725_02
Create Date: 2026-07-27 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_03"
down_revision: Union[str, None] = "20260725_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("teacher_score", sa.Float(), nullable=True),
        sa.Column("score_delta", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "user_id", "source",
            name="uq_agent_feedback_run_user_source",
        ),
    )
    op.create_index(
        op.f("ix_agent_feedback_run_id"), "agent_feedback", ["run_id"],
    )
    op.create_index(
        op.f("ix_agent_feedback_user_id"), "agent_feedback", ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_feedback_user_id"), table_name="agent_feedback")
    op.drop_index(op.f("ix_agent_feedback_run_id"), table_name="agent_feedback")
    op.drop_table("agent_feedback")
