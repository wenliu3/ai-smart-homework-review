"""multi dimension grading

多维度评分标准（规划：多维度评分功能）：
- ai_rules 增加 criteria JSON 列：多维度评分项配置（每项 id/title/maxScore/instructions）；
  空或缺失时批改回退单维度 overall。
- submissions 增加 ai_review_items JSON 列：落库 GradingDraft.items 的分项数组
  （criterion_id/title/score/max_score/feedback/evidence_refs），学生端按维度展示。

Revision ID: b7e3f6a2d1c5
Revises: e2b6c9d4a7f1
Create Date: 2026-08-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3f6a2d1c5'
down_revision: Union[str, None] = 'e2b6c9d4a7f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_rules',
        sa.Column('criteria', sa.JSON(), nullable=True),
    )
    op.add_column(
        'submissions',
        sa.Column('ai_review_items', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('submissions', 'ai_review_items')
    op.drop_column('ai_rules', 'criteria')
