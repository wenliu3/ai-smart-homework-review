"""assignment soft delete

给 assignments 增加 deleted_at 软删列（规划阶段 3A.2 / 决策 D1）：
审批后执行的删除作业动作只置该列，不物理删除作业与提交记录。

Revision ID: a1c7f2d4b8e3
Revises: 9e5b9284446d
Create Date: 2026-07-26 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c7f2d4b8e3'
down_revision: Union[str, None] = '9e5b9284446d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'assignments',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f('ix_assignments_deleted_at'),
        'assignments',
        ['deleted_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_assignments_deleted_at'), table_name='assignments')
    op.drop_column('assignments', 'deleted_at')
