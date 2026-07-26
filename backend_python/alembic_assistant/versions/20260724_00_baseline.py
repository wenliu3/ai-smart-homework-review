"""PostgreSQL Agent 状态库基线。

Revision ID: 20260724_00
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_00"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_chat_messages_teacher_id", "agent_chat_messages", ["teacher_id"])
    op.create_index("ix_agent_chat_messages_session_id", "agent_chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_chat_messages_session_id", table_name="agent_chat_messages")
    op.drop_index("ix_agent_chat_messages_teacher_id", table_name="agent_chat_messages")
    op.drop_table("agent_chat_messages")
