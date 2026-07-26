"""ai model capabilities

给 ai_models 增加能力标签与档位绑定列（规划阶段 5.3）：
capabilities 存 ["text","vision"]，profile_bindings 存 {"vision_grader": true}，
支撑 VISION_GRADER 等档位按能力选模型与后续备用模型切换。

Revision ID: e2b6c9d4a7f1
Revises: c4e9a1b6d2f8
Create Date: 2026-07-27 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2b6c9d4a7f1'
down_revision: Union[str, None] = 'c4e9a1b6d2f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_models', sa.Column('capabilities', sa.JSON(), nullable=True),
    )
    op.add_column(
        'ai_models', sa.Column('profile_bindings', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('ai_models', 'profile_bindings')
    op.drop_column('ai_models', 'capabilities')
