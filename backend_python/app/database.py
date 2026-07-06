"""SQLAlchemy 数据库连接与会话管理"""
import re
import urllib.parse
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings


def _ensure_database():
    """连接 MySQL 并自动创建目标数据库(若不存在),避免手动执行 SQL。"""
    url = settings.DATABASE_URL
    # 解析 mysql+pymysql://user:pass@host:port/dbname?params
    pattern = r"^mysql\+pymysql://([^:]+):([^@]*)@([^:/]+)(?::(\d+))?/([^?]*)(\?.*)?$"
    m = re.match(pattern, url)
    if not m:
        return  # 非标准 URL，跳过自动建库
    user = m.group(1)
    pwd = urllib.parse.unquote(m.group(2))
    host = m.group(3)
    port = int(m.group(4) or 3306)
    db_name = m.group(5)

    conn = pymysql.connect(host=host, user=user, password=pwd, port=port)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


_ensure_database()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖: 获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
