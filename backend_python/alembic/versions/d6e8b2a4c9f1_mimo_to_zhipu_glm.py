"""replace xiaomi mimo with zhipu glm-5.3-flash

将预置 AI 模型「小米 MiMo」整体替换为「智谱 GLM-5.3-Flash」：
- ai_rules.model_type = 'mimo' 的引用同步改为 'zhipu'；
- ai_models 中 code='mimo' 的行就地改写为 zhipu/glm-5.3-flash（保留
  status/is_default 以实现无缝切换）；旧密钥对智谱无效故清空，
  用量/余额为原供应商的历史数据一并清零。

Revision ID: d6e8b2a4c9f1
Revises: f8d2a4c1e9b3
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd6e8b2a4c9f1'
down_revision: Union[str, None] = 'f8d2a4c1e9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upgrade_row(conn) -> None:
    if conn.execute(
        sa.text("SELECT 1 FROM ai_models WHERE code = 'zhipu' LIMIT 1")
    ).scalar():
        # 已存在智谱配置：删除小米旧行，避免 code 唯一冲突
        conn.execute(sa.text("DELETE FROM ai_models WHERE code = 'mimo'"))
        return
    conn.execute(sa.text("""
        UPDATE ai_models
        SET code = 'zhipu',
            name = '智谱GLM',
            provider = '智谱',
            model_name = 'glm-5.3-flash',
            base_url = 'https://open.bigmodel.cn/api/paas/v4',
            api_key = '',
            total_usage = 0,
            total_tokens = 0,
            last_used_at = NULL,
            last_balance = 0,
            balance_currency = 'CNY',
            last_balance_check = NULL
        WHERE code = 'mimo'
    """))


def upgrade() -> None:
    conn = op.get_bind()
    # ai_rules.model_type 为普通字符串列（无外键），先改引用再换模型行
    conn.execute(sa.text("UPDATE ai_rules SET model_type = 'zhipu' WHERE model_type = 'mimo'"))
    _upgrade_row(conn)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE ai_rules SET model_type = 'mimo' WHERE model_type = 'zhipu'"))
    if conn.execute(
        sa.text("SELECT 1 FROM ai_models WHERE code = 'mimo' LIMIT 1")
    ).scalar():
        conn.execute(sa.text("DELETE FROM ai_models WHERE code = 'zhipu'"))
        return
    # 注意：api_key/用量/余额无法从迁移中恢复，需在管理页重新填写
    conn.execute(sa.text("""
        UPDATE ai_models
        SET code = 'mimo',
            name = '小米',
            provider = '小米',
            model_name = 'mimo-v2.5',
            base_url = 'https://api.xiaomimimo.com/v1'
        WHERE code = 'zhipu'
    """))
