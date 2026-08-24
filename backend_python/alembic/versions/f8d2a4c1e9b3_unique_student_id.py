"""unique student id

给 users.student_id 增加唯一索引：学号按唯一处理（业务原则）。
迁移执行前会先检查既有重复数据——如存在重复学号，迁移会失败并列出重复项，
此时不允许自动删除/覆盖用户，需人工处理重复学号后再执行本迁移。

Revision ID: f8d2a4c1e9b3
Revises: b7e3f6a2d1c5
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8d2a4c1e9b3'
down_revision: Union[str, None] = 'b7e3f6a2d1c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 先检查重复学号：存在重复时中止迁移（不允许自动删除/覆盖用户数据）
    conn = op.get_bind()
    duplicates = conn.execute(sa.text(
        "SELECT student_id, COUNT(*) AS cnt FROM users "
        "WHERE student_id IS NOT NULL AND student_id <> '' "
        "GROUP BY student_id HAVING COUNT(*) > 1 ORDER BY cnt DESC"
    )).fetchall()
    if duplicates:
        detail = ", ".join(f"{row.student_id}(x{row.cnt})" for row in duplicates[:20])
        raise RuntimeError(
            f"users.student_id 存在 {len(duplicates)} 组重复数据，无法安全添加唯一索引；"
            f"请先人工处理重复学号（示例: {detail}）"
        )

    op.create_index(
        op.f('uq_users_student_id'),
        'users',
        ['student_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f('uq_users_student_id'), table_name='users')
