"""fix assignment ai_rule snapshots referencing mimo

历史作业创建时把规则打成了 JSON 快照（assignments.ai_rule），其中
modelType="mimo" 的快照不随 ai_rules 表迁移自动更新；模型行已改写为
zhipu 后，这些作业发起批改会因按 code 精确路由（不回退默认模型）
而受控失败。本迁移把快照顶层的 $.modelType 由 mimo 改为 zhipu。

Revision ID: b3d7e1f9c4a2
Revises: d6e8b2a4c9f1
Create Date: 2026-08-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3d7e1f9c4a2'
down_revision: Union[str, None] = 'd6e8b2a4c9f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # 跨方言（MySQL/SQLite）字符串替换：快照 JSON 里 modelType 只在顶层出现，
    # 直接替换键值对不会误伤其他字段；兼容带空格/不带空格两种序列化格式。
    conn.execute(sa.text(
        "UPDATE assignments SET ai_rule = REPLACE(REPLACE(ai_rule, "
        "'\"modelType\": \"mimo\"', '\"modelType\": \"zhipu\"'), "
        "'\"modelType\":\"mimo\"', '\"modelType\":\"zhipu\"') "
        "WHERE ai_rule LIKE '%\"modelType\": \"mimo\"%' "
        "OR ai_rule LIKE '%\"modelType\":\"mimo\"%'"
    ))


def downgrade() -> None:
    # 有意留空：快照 mimo→zhipu 无法与"本就绑定 zhipu 的作业"区分，
    # 反向改写会误伤新数据，属有损回滚，不做。
    pass
