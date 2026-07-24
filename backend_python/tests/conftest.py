"""pytest 全局夹具：隔离 SQLite 测试库、TestClient、用户/令牌/AI 模型工厂。

DATABASE_URL 必须在导入任何 app 模块之前设置：
settings 在 app.config 导入时读取环境变量；sqlite URL 会让
app.database._ensure_database() 正则不匹配直接跳过，完全不触达 MySQL。
"""
import os
from pathlib import Path

_TEST_DB_PATH = Path(__file__).parent / ".pytest.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine
from app.models import AiModel, User


def _truncate_all_tables() -> None:
    """清空全部表（按外键反向顺序），避免重复书写 setup/teardown 清空逻辑。"""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前建表+清空、测试后再清空，保证用例隔离（含上次 pytest 中断残留）。"""
    Base.metadata.create_all(bind=engine)
    _truncate_all_tables()
    yield
    _truncate_all_tables()


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user_factory(db):
    def _make(username: str, role: str) -> User:
        user = User(
            username=username,
            email=f"{username}@test.local",
            password=hash_password("test-password"),
            name=username,
            role=role,
            status="active",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    return _make


@pytest.fixture()
def teacher(user_factory):
    return user_factory("t_alice", "teacher")


@pytest.fixture()
def student(user_factory):
    return user_factory("s_bob", "student")


@pytest.fixture()
def auth_header():
    def _header(user: User) -> dict:
        token = create_access_token(sub=str(user.id), username=user.username, role=user.role)
        return {"Authorization": f"Bearer {token}"}
    return _header


@pytest.fixture()
def ai_model_factory(db):
    def _make(code: str = "deepseek-chat", name: str = "DeepSeek",
              is_default: bool = True, api_key: str = "sk-test-0123456789abcdef",
              status: str = "active") -> AiModel:
        model = AiModel(
            code=code, name=name, provider="deepseek", model_name=code,
            base_url="https://api.deepseek.com/v1", api_key=api_key,
            status=status, is_default=is_default,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model
    return _make
