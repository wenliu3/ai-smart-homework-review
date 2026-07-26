"""AI 助手状态库（PostgreSQL）连接与会话管理。

与业务库（MySQL，app.database）物理隔离：
- 业务数据（用户/班级/作业/提交/模型配置）→ MySQL
- AI 助手聊天历史和 Agent 运行状态 → PostgreSQL

数据库和表由 Docker/PostgreSQL Alembic 迁移负责创建，应用导入不执行 DDL。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

assistant_engine = create_engine(
    settings.ASSISTANT_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    # 连接池容量 pool_size + max_overflow = 15：
    # AGENT_STREAM_MAX_CONCURRENCY（config.py，默认 12）必须低于该值，
    # 否则流式 worker 满载时会阻塞等待连接直至池超时（默认 30 秒）。
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
