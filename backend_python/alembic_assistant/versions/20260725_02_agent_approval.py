"""新增 Agent 写操作审批记录。

Revision ID: 20260725_02
Revises: 20260724_01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260725_02"
down_revision: Union[str, None] = "20260724_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("requester_role", sa.String(length=20), nullable=False),
        sa.Column("approver_user_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agent_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_agent_approvals_run_id",
        "agent_approvals",
        ["run_id"],
    )
    op.create_index(
        "ix_agent_approvals_requester_user_id",
        "agent_approvals",
        ["requester_user_id"],
    )
    op.create_index(
        "ix_agent_approvals_idempotency_key",
        "agent_approvals",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_agent_approvals_status",
        "agent_approvals",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_approvals_status", table_name="agent_approvals")
    op.drop_index(
        "ix_agent_approvals_idempotency_key",
        table_name="agent_approvals",
    )
    op.drop_index(
        "ix_agent_approvals_requester_user_id",
        table_name="agent_approvals",
    )
    op.drop_index("ix_agent_approvals_run_id", table_name="agent_approvals")
    op.drop_table("agent_approvals")
