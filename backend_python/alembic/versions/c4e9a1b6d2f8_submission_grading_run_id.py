"""submission grading run id

给 submissions 增加 grading_run_id 列（规划阶段 3B.3）：
记录最近一次 AI 批改运行 ID，学生轮询进度与教师查看分维度产物由此定位。

Revision ID: c4e9a1b6d2f8
Revises: a1c7f2d4b8e3
Create Date: 2026-07-26 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e9a1b6d2f8'
down_revision: Union[str, None] = 'a1c7f2d4b8e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'submissions',
        sa.Column('grading_run_id', sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f('ix_submissions_grading_run_id'),
        'submissions',
        ['grading_run_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_submissions_grading_run_id'), table_name='submissions',
    )
    op.drop_column('submissions', 'grading_run_id')
