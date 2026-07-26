"""pytest 全局夹具：双库（MySQL/PG 均用 SQLite 替身）隔离、TestClient、工厂夹具。

DATABASE_URL / ASSISTANT_DATABASE_URL 必须在导入任何 app 模块之前设置：
settings 在 app.config 导入时读取环境变量；sqlite URL 会让两个
_ensure_database() 正则不匹配直接跳过，完全不触达 MySQL/PostgreSQL。
"""
import os
from pathlib import Path

_TEST_DIR = Path(__file__).parent
# 文件名带 PID：允许多个 pytest 进程并行运行而不互踩同一 sqlite 文件
_BIZ_DB = _TEST_DIR / f".pytest_biz-{os.getpid()}.db"
_ASSISTANT_DB = _TEST_DIR / f".pytest_assistant-{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_BIZ_DB.as_posix()}"
os.environ["ASSISTANT_DATABASE_URL"] = f"sqlite:///{_ASSISTANT_DB.as_posix()}"

import pytest
from fastapi.testclient import TestClient

from app.assistant_database import AssistantBase, AssistantSessionLocal, assistant_engine
from app.core.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine
from app.models import AiModel, User


def _truncate_all(engine_, metadata) -> None:
    """清空指定库的全部表（按外键反向顺序），setup/teardown 复用。"""
    with engine_.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前建表+清空、测试后再清空（双库），保证用例隔离（含上次中断残留）。"""
    Base.metadata.create_all(bind=engine)
    AssistantBase.metadata.create_all(bind=assistant_engine)
    _truncate_all(engine, Base.metadata)
    _truncate_all(assistant_engine, AssistantBase.metadata)
    yield
    _truncate_all(engine, Base.metadata)
    _truncate_all(assistant_engine, AssistantBase.metadata)


@pytest.fixture()
def db():
    """业务库（MySQL）会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def assistant_db():
    """会话库（PostgreSQL）会话。"""
    session = AssistantSessionLocal()
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


def pytest_sessionfinish(session, exitstatus):
    """会话结束后释放引擎并删除本进程的 sqlite 临时库文件。"""
    engine.dispose()
    assistant_engine.dispose()
    for path in (_BIZ_DB, _ASSISTANT_DB):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
