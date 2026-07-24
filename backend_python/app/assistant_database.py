"""AI 助手会话库（PostgreSQL）连接与会话管理。

与业务库（MySQL，app.database）物理隔离：
- 业务数据（用户/班级/作业/提交/模型配置）→ MySQL
- AI 助手聊天历史（agent_chat_messages，阶段 1 起 agent_sessions 等）→ PostgreSQL

自动建库模式与 app.database._ensure_database() 一致：非 PostgreSQL URL 直接跳过。
"""
import re
import urllib.parse

import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _ensure_assistant_database():
    """连接 PostgreSQL 并自动创建目标数据库（若不存在）。"""
    url = settings.ASSISTANT_DATABASE_URL
    # 解析 postgresql://user:pass@host:port/dbname?params
    pattern = r"^postgresql://([^:]+):([^@]*)@([^:/]+)(?::(\d+))?/([^?]*)(\?.*)?$"
    m = re.match(pattern, url)
    if not m:
        return  # 非标准 URL（如测试用 sqlite），跳过自动建库
    user = m.group(1)
    pwd = urllib.parse.unquote(m.group(2))
    host = m.group(3)
    port = int(m.group(4) or 5432)
    db_name = m.group(5)

    conn = psycopg2.connect(host=host, user=user, password=pwd, port=port, dbname="postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()


_ensure_assistant_database()

assistant_engine = create_engine(
    settings.ASSISTANT_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

AssistantSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=assistant_engine)


class AssistantBase(DeclarativeBase):
    pass


def get_assistant_db():
    """FastAPI 依赖：获取会话库会话"""
    db = AssistantSessionLocal()
    try:
        yield db
    finally:
        db.close()
