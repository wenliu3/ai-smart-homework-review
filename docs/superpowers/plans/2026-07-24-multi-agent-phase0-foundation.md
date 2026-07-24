# 多智能体平台阶段 0（基础治理）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在不改变现有教师助手外部行为的前提下，建立多智能体平台的共同前提：Alembic 迁移基线、pytest 测试体系、Pydantic Agent 契约、统一模型网关、Prompt 版本管理，并修复助手路由的角色校验缺失与 SSE 错误信息泄露。

**架构：** 对应规格文档 `docs/superpowers/specs/2026-07-24-multi-agent-platform-design.md` 第 21 节「阶段 0」，并按 2026-07-24 确认的调整落地**双库架构**：AI 助手聊天历史（`agent_chat_messages`，阶段 1 起 `agent_sessions` 等会话表）存储到 PostgreSQL 的 `ai_smart_review` 库；业务数据（用户/班级/作业/提交/模型配置）继续存储在 MySQL。现有单 Agent（`app/agent/agent.py`）保留为唯一 Agent，但其 ChatModel 创建改走新的 `ModelGateway`（多维缓存键），系统 Prompt 改走 `PromptRegistry`（版本化）；`routers/chat.py` 的业务逻辑下沉到 `crud/agent_chat.py` 与 `agent/service.py`，路由回归薄层。阶段 1 的多 Agent 拆分不在本计划范围内。

**技术栈：** FastAPI 0.139（`fastapi.sse`）、SQLAlchemy 2.0、PostgreSQL（psycopg2-binary，会话库，Docker 启动）+ MySQL（业务库）、Alembic 1.14、pytest 8.3、LangChain 1.3（`create_agent` + `init_chat_model`）、SQLite（两个测试库替身，通过环境变量切换）。

**存储决策（2026-07-24 确认）：**
- 会话库连接：`postgresql://langgraph_user:123456@localhost:5432/ai_smart_review?sslmode=disable`，配置项为 `ASSISTANT_DATABASE_URL`；数据库 `ai_smart_review` 由后端启动时自动创建（参照现有 MySQL `_ensure_database()` 模式）。
- 迁移策略：MySQL 用 Alembic 管理（任务 3 基线）；PostgreSQL 会话库本阶段用 `AssistantBase.metadata.create_all()` 自动建表（与项目现有风格一致），阶段 1 引入 `agent_sessions` 等新表时再把 PG 纳入 Alembic 多链管理。
- MySQL 中已有的旧 `agent_chat_messages` 表：提供一次性迁移脚本把历史聊天复制到 PG（任务 2 步骤 7，可选执行）；旧表成为 Alembic 不管辖的游离表，阶段 1 用独立迁移删除。

---

## 现状关键事实（实现前必读）

- `backend_python/app/agent/agent.py`：`_get_agent(db)` 用进程级缓存（key=默认模型 id + 60s TTL），`chat_with_agent()` 只透传 `AIMessageChunk.text`。
- `backend_python/app/agent/tools.py`：7 个查询工具返回拼接字符串，`ToolRuntime[TeacherContext]` 注入 `teacher_id`。**本阶段不改动 tools.py**（结构化改造属阶段 1）。
- `backend_python/app/routers/chat.py`：路由内直接查库、存消息、拼 SSE；`Depends(get_current_user)` 未校验角色；`except Exception` 把 `f"{type(e).__name__}: {e}"` 直接发给前端（泄露内部实现）。
- `backend_python/app/database.py`：模块导入时执行 `_ensure_database()`，对非 `mysql+pymysql://` URL 直接跳过——因此测试可用 `DATABASE_URL=sqlite:///...` 完全避开 MySQL。会话库（PostgreSQL）采用同样的自动建库模式（任务 2），测试用 `ASSISTANT_DATABASE_URL=sqlite:///...` 避开 PG。
- `backend_python/app/models/agent_chat_message.py`：`AgentChatMessage` 当前继承 `Base`（MySQL），`teacher_id` 带 `ForeignKey("users.id")`——迁移到 PG 时必须去掉跨库物理外键，保留普通索引列。
- `backend_python/app/models/`：12 张表：`users, refresh_tokens, classes, class_students, assignments, submissions, ai_models, ai_rules, menus, roles, agent_chat_messages, operation_logs`。`User` 必填字段：`username, email, password, name`。`TimestampMixin.updated_at` 为 `server_default=func.now(), onupdate=func.now()`（秒级精度）。
- `backend_python/app/deps.py`：已有 `require_roles(*roles)` 工厂，直接复用。
- `backend_python/app/core/exceptions.py`：`BizException(code, message, status_code=400)` 及子类；`app/main.py` 有全局处理器返回 `{code, message}`。
- 项目无 pytest、无 Alembic；`backend_python/tests/` 仅有一个脚本式 `test_image_plagiarism.py`（保留不动，在 `pytest.ini` 中排除收集）。
- 运行环境为 Windows PowerShell，以下命令均在 `backend_python/` 目录下执行（git 命令除外）。

## 文件结构

**创建：**

| 文件 | 职责 |
|---|---|
| `backend_python/requirements-dev.txt` | 开发依赖（pytest），含 `-r requirements.txt` |
| `backend_python/pytest.ini` | pytest 配置 |
| `backend_python/app/assistant_database.py` | PostgreSQL 会话库：engine、`AssistantBase`、`AssistantSessionLocal`、`get_assistant_db`、自动建库 |
| `backend_python/scripts/__init__.py`、`scripts/migrate_agent_chat_to_pg.py` | 一次性历史聊天迁移脚本（MySQL → PG，幂等，可选执行） |
| `backend_python/alembic.ini` + `backend_python/alembic/{env.py,script.py.mako,versions/}` | Alembic 迁移体系（仅 MySQL 业务库） |
| `backend_python/tests/__init__.py`、`tests/unit/__init__.py`、`tests/unit/agent/__init__.py`、`tests/integration/__init__.py`、`tests/integration/agent/__init__.py` | 测试包 |
| `backend_python/tests/conftest.py` | 双库（MySQL/PG 均用 SQLite 替身）隔离 + 用户/令牌/AI 模型工厂夹具 |
| `backend_python/tests/fakes.py` | `FakeAgent`（假模型，替代真实 langgraph agent） |
| `backend_python/tests/test_smoke.py` | 基础设施冒烟测试 |
| `backend_python/tests/unit/test_assistant_database.py` | 会话库归属、无跨库外键、读写、启动建表测试 |
| `backend_python/tests/unit/test_alembic_migrations.py` | 基线迁移 upgrade/downgrade 测试（11 张 MySQL 表） |
| `backend_python/tests/unit/agent/test_contracts.py` | 契约校验测试 |
| `backend_python/tests/unit/agent/test_prompt_registry.py` | Prompt 注册表测试 |
| `backend_python/tests/unit/agent/test_model_gateway.py` | 模型网关测试 |
| `backend_python/tests/unit/agent/test_agent_chat_crud.py` | 会话 CRUD 测试 |
| `backend_python/tests/integration/agent/test_assistant_service.py` | 对话编排服务测试 |
| `backend_python/tests/integration/agent/test_chat_api.py` | 助手 API/SSE/权限测试 |
| `backend_python/app/agent/contracts.py` | Pydantic 契约：`ActorContext`、`ModelProfile`、`AgentError`、`UsageSummary`、稳定错误码 |
| `backend_python/app/agent/prompts/{__init__.py,registry.py,teacher_assistant.py}` | Prompt 版本注册表 + `teacher_assistant:v1` |
| `backend_python/app/agent/services/{__init__.py,model_gateway.py}` | 统一模型网关（含全局单例 `model_gateway`） |
| `backend_python/app/agent/service.py` | 对话编排服务 `stream_chat_events()` + `ChatStreamEvent` |
| `backend_python/app/crud/agent_chat.py` | 会话消息数据访问 |

**修改：**

| 文件 | 改动 |
|---|---|
| `backend_python/requirements.txt` | 追加 `alembic==1.14.1`、`psycopg2-binary==2.9.10` |
| `backend_python/app/config.py` | 追加 `ASSISTANT_DATABASE_URL` 配置项 |
| `backend_python/.env.example` | 追加 `ASSISTANT_DATABASE_URL` 示例 |
| `backend_python/app/models/agent_chat_message.py` | 改继承 `AssistantBase`，去掉跨库 `ForeignKey("users.id")` |
| `backend_python/app/main.py` | 启动时 `AssistantBase.metadata.create_all()` |
| `backend_python/app/agent/agent.py` | 删除本地 SYSTEM_PROMPT/缓存 TTL，改走 ModelGateway + PromptRegistry；对外函数签名不变 |
| `backend_python/app/routers/chat.py` | 薄路由化：`require_roles("teacher")` + 委托 service/crud（会话接口用 `get_assistant_db`）；删除全部业务逻辑 |

---

## 任务 0：提交改造前基线

工作区现有未提交修改（`agent.py`、`tools.py`、`chat.py` 的近期调整及 superpowers 框架文件），先提交，保证本计划的每一步 diff 清晰、可回退。

**文件：** 无（仅 git 操作）

- [ ] **步骤 1：提交基线**

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review"
git add backend_python/app/agent/agent.py backend_python/app/agent/tools.py backend_python/app/routers/chat.py
git commit -m "refactor: 多智能体改造前的助手代码基线"
git add .agents AGENTS.md docs/superpowers
git commit -m "docs: 引入 superpowers 技能框架与多智能体架构设计文档"
```

---

## 任务 1：pytest 测试基础设施

**文件：**
- 创建：`backend_python/requirements-dev.txt`
- 创建：`backend_python/pytest.ini`
- 创建：`backend_python/tests/__init__.py`（空文件）
- 创建：`backend_python/tests/conftest.py`
- 创建：`backend_python/tests/fakes.py`
- 创建：`backend_python/tests/test_smoke.py`

- [ ] **步骤 1：创建开发依赖文件并安装**

`backend_python/requirements-dev.txt`：

```text
-r requirements.txt
pytest==8.3.5
```

运行：

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review\backend_python"
pip install -r requirements-dev.txt
```

预期：pytest 8.3.5 安装成功。

- [ ] **步骤 2：创建 pytest.ini**

`backend_python/pytest.ini`：

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -ra --ignore=tests/test_image_plagiarism.py
```

- [ ] **步骤 3：编写 conftest、fakes 与冒烟测试**

`backend_python/tests/conftest.py`：

```python
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


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前建表、测试后清空全部表，保证用例隔离。"""
    Base.metadata.create_all(bind=engine)
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


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
```

`backend_python/tests/fakes.py`：

```python
"""测试假件（假模型/假 Agent）：保证测试不依赖外部 AI API。"""
from langchain_core.messages import AIMessageChunk


class FakeAgent:
    """模拟 langgraph agent.stream 的输出协议：迭代 (AIMessageChunk, metadata)。

    chunks: 依次产出的文本分片；error: 非空时 stream 开始即抛出。
    received_input / received_context: 记录调用入参，供断言上下文注入。
    """

    def __init__(self, chunks=(), error=None):
        self.chunks = list(chunks)
        self.error = error
        self.received_input = None
        self.received_context = None

    def stream(self, input, context=None, stream_mode=None):
        self.received_input = input
        self.received_context = context
        if self.error:
            raise self.error
        for text in self.chunks:
            yield (AIMessageChunk(content=text), {})
```

`backend_python/tests/test_smoke.py`：

```python
"""测试基础设施冒烟：夹具可用、应用可导入、测试库隔离生效。"""
from app.models import User


def test_db_fixture_creates_user(db, user_factory):
    user = user_factory("smoke_teacher", "teacher")
    assert user.id is not None
    assert db.query(User).filter_by(username="smoke_teacher").count() == 1


def test_client_serves_api_docs(client):
    resp = client.get("/api/docs")
    assert resp.status_code == 200


def test_db_is_clean_between_tests(db):
    assert db.query(User).count() == 0
```

- [ ] **步骤 4：运行冒烟测试确认通过**

运行：`python -m pytest tests/test_smoke.py -v`
预期：3 个测试全部 PASS。

- [ ] **步骤 5：Commit**

```powershell
git add backend_python/requirements-dev.txt backend_python/pytest.ini backend_python/tests
git commit -m "test: 引入 pytest 测试基础设施（SQLite 隔离库 + 工厂夹具 + 假 Agent）"
```

---

## 任务 2：PostgreSQL 会话库接入（双库架构）

按 2026-07-24 确认的存储决策：AI 助手聊天历史存 PostgreSQL `ai_smart_review` 库，业务数据留 MySQL。`AgentChatMessage` 从 MySQL 的 `Base` 迁到 PG 的 `AssistantBase`，去掉跨库物理外键；PG 库与表在启动时自动创建（沿用项目现有 `_ensure_database` + `create_all` 模式），Alembic 只管 MySQL。

**文件：**
- 修改：`backend_python/requirements.txt`（追加 psycopg2-binary）
- 修改：`backend_python/app/config.py`（追加 `ASSISTANT_DATABASE_URL`）
- 修改：`backend_python/.env.example`（追加示例）
- 创建：`backend_python/app/assistant_database.py`
- 修改：`backend_python/app/models/agent_chat_message.py`（整体替换）
- 修改：`backend_python/app/main.py`（追加 2 行）
- 修改：`backend_python/tests/conftest.py`（双库隔离 + `assistant_db` 夹具）
- 创建：`backend_python/scripts/__init__.py`（空文件）、`backend_python/scripts/migrate_agent_chat_to_pg.py`
- 测试：`backend_python/tests/unit/test_assistant_database.py`

- [ ] **步骤 1：安装 PostgreSQL 驱动**

修改 `backend_python/requirements.txt`，在末尾追加：

```text
psycopg2-binary==2.9.10
```

运行：`pip install psycopg2-binary==2.9.10`
预期：安装成功。

- [ ] **步骤 2：添加配置项**

`backend_python/app/config.py` 在 `DATABASE_URL` 行后追加：

```python
    # AI 助手会话库（PostgreSQL）：存储 AI 聊天历史；业务数据仍在 MySQL
    ASSISTANT_DATABASE_URL: str = "postgresql://langgraph_user:123456@localhost:5432/ai_smart_review?sslmode=disable"
```

`backend_python/.env.example` 在 `DATABASE_URL` 行后追加：

```text
ASSISTANT_DATABASE_URL=postgresql://langgraph_user:123456@localhost:5432/ai_smart_review?sslmode=disable
```

- [ ] **步骤 3：编写失败的测试**

`backend_python/tests/unit/test_assistant_database.py`：

```python
"""会话库（PostgreSQL，测试用 SQLite 替身）接入测试。

验证双库边界：AgentChatMessage 归属 AssistantBase、无跨库外键、
可读写、应用启动时自动建表。
"""
from sqlalchemy import inspect

from app.assistant_database import AssistantBase, assistant_engine
from app.database import Base
from app.models import AgentChatMessage


def test_agent_chat_message_belongs_to_assistant_base():
    assert "agent_chat_messages" in AssistantBase.metadata.tables
    assert "agent_chat_messages" not in Base.metadata.tables


def test_agent_chat_message_has_no_cross_db_foreign_key():
    table = AssistantBase.metadata.tables["agent_chat_messages"]
    assert list(table.c.teacher_id.foreign_keys) == []
    # teacher_id 保留索引（按教师查会话是高频条件）
    assert any(ix.columns.get("teacher_id") is not None for ix in table.indexes)


def test_insert_and_read_message(assistant_db):
    assistant_db.add(AgentChatMessage(teacher_id=1, session_id="s1", role="user", content="你好"))
    assistant_db.commit()
    rows = assistant_assistant_db.query(AgentChatMessage).filter_by(session_id="s1").all()
    assert len(rows) == 1
    assert rows[0].content == "你好"


def test_startup_creates_assistant_tables(client):
    insp = inspect(assistant_engine)
    assert "agent_chat_messages" in insp.get_table_names()
```

- [ ] **步骤 4：运行测试验证失败**

运行：`python -m pytest tests/unit/test_assistant_database.py -v`
预期：collection ERROR，`ModuleNotFoundError: No module named 'app.assistant_database'`，且 conftest 尚无 `assistant_db` 夹具。

- [ ] **步骤 5：实现会话库、模型迁移与 conftest 双库隔离**

创建 `backend_python/app/assistant_database.py`：

```python
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
```

**整体替换** `backend_python/app/models/agent_chat_message.py`：

```python
"""AI 助手聊天消息（存储于 PostgreSQL 会话库，与 MySQL 业务库物理隔离）"""
from sqlalchemy import Column, Integer, String, Text
from ..assistant_database import AssistantBase
from .base import TimestampMixin, ModelMixin


class AgentChatMessage(AssistantBase, TimestampMixin, ModelMixin):
    __tablename__ = "agent_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 逻辑关联 users.id（跨库不加物理外键，由应用层保证归属校验）
    teacher_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
```

`backend_python/app/main.py` 修改两处：

```python
# 第 10 行改为：
from .database import engine, Base, SessionLocal
from .assistant_database import AssistantBase, assistant_engine

# 第 20 行 `Base.metadata.create_all(bind=engine)` 后追加：
AssistantBase.metadata.create_all(bind=assistant_engine)  # AI 助手会话库（PostgreSQL）
```

**整体替换** `backend_python/tests/conftest.py`：

```python
"""pytest 全局夹具：双库（MySQL/PG 均用 SQLite 替身）隔离、TestClient、工厂夹具。

DATABASE_URL / ASSISTANT_DATABASE_URL 必须在导入任何 app 模块之前设置：
settings 在 app.config 导入时读取环境变量；sqlite URL 会让两个
_ensure_database() 正则不匹配直接跳过，完全不触达 MySQL/PostgreSQL。
"""
import os
from pathlib import Path

_TEST_DIR = Path(__file__).parent
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / '.pytest_biz.db').as_posix()}"
os.environ["ASSISTANT_DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / '.pytest_assistant.db').as_posix()}"

import pytest
from fastapi.testclient import TestClient

from app.assistant_database import AssistantBase, AssistantSessionLocal, assistant_engine
from app.core.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine
from app.models import AiModel, User


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前建表、测试后清空两个库的全部表，保证用例隔离。"""
    Base.metadata.create_all(bind=engine)
    AssistantBase.metadata.create_all(bind=assistant_engine)
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    with assistant_engine.begin() as conn:
        for table in reversed(AssistantBase.metadata.sorted_tables):
            conn.execute(table.delete())


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
```

- [ ] **步骤 6：运行全部测试验证通过**

运行：`python -m pytest tests -v`
预期：任务 1 的冒烟测试 + 本任务 4 项测试全部 PASS。

- [ ] **步骤 7：创建一次性历史聊天迁移脚本（可选执行）**

创建空文件 `backend_python/scripts/__init__.py`。

`backend_python/scripts/migrate_agent_chat_to_pg.py`：

```python
"""一次性迁移：MySQL agent_chat_messages → PostgreSQL 会话库（幂等，可重复执行）。

用法（backend_python 目录）：
    python -m scripts.migrate_agent_chat_to_pg

模型已迁移到 AssistantBase，MySQL 旧表通过 Core 反射读取，不依赖 ORM。
判重键：(teacher_id, session_id, role, content, created_at)。
"""
from sqlalchemy import MetaData, Table, create_engine, select

from app.assistant_database import AssistantBase, AssistantSessionLocal, assistant_engine
from app.config import settings
from app.models import AgentChatMessage


def main() -> None:
    src = create_engine(settings.DATABASE_URL)
    meta = MetaData()
    try:
        legacy = Table("agent_chat_messages", meta, autoload_with=src)
    except Exception:
        print("MySQL 中不存在 agent_chat_messages 表，无需迁移")
        return

    AssistantBase.metadata.create_all(bind=assistant_engine)
    with src.connect() as sconn, AssistantSessionLocal() as tconn:
        rows = sconn.execute(select(legacy)).mappings().all()
        if not rows:
            print("MySQL agent_chat_messages 无数据，无需迁移")
            return
        existing = {
            (m.teacher_id, m.session_id, m.role, m.content, m.created_at)
            for m in tconn.query(AgentChatMessage).all()
        }
        inserted = 0
        for r in rows:
            key = (r["teacher_id"], r["session_id"], r["role"], r["content"], r["created_at"])
            if key in existing:
                continue
            tconn.add(AgentChatMessage(
                teacher_id=r["teacher_id"], session_id=r["session_id"],
                role=r["role"], content=r["content"],
                created_at=r["created_at"], updated_at=r["updated_at"],
            ))
            inserted += 1
        tconn.commit()
        print(f"迁移完成：MySQL 共 {len(rows)} 条，新增 {inserted} 条，跳过 {len(rows) - inserted} 条")


if __name__ == "__main__":
    main()
```

若开发库有值得保留的历史聊天，执行（先确认 Docker 中 PostgreSQL 已启动）：

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review\backend_python"
python -m scripts.migrate_agent_chat_to_pg
```

预期：输出迁移条数。MySQL 旧表保留不动（游离表），阶段 1 用独立迁移删除。

- [ ] **步骤 8：Commit**

```powershell
git add backend_python/requirements.txt backend_python/app/config.py backend_python/.env.example backend_python/app/assistant_database.py backend_python/app/models/agent_chat_message.py backend_python/app/main.py backend_python/tests/conftest.py backend_python/tests/unit/test_assistant_database.py backend_python/scripts
git commit -m "feat: AI 助手聊天历史迁移到 PostgreSQL 会话库（双库架构）"
```

---

## 任务 3：Alembic 数据库基线

**文件：**
- 修改：`backend_python/requirements.txt`（追加一行）
- 创建：`backend_python/alembic.ini`、`backend_python/alembic/env.py`、`backend_python/alembic/script.py.mako`（init 生成）、`backend_python/alembic/versions/<rev>_baseline.py`（autogenerate）
- 测试：`backend_python/tests/unit/__init__.py`（空文件）、`backend_python/tests/unit/test_alembic_migrations.py`

说明：Alembic 只管理 MySQL 业务库（11 张表；`agent_chat_messages` 已于任务 2 迁往 PostgreSQL，不在 MySQL metadata 中）。PG 会话库的表由启动时 `create_all` 创建，阶段 1 再纳入迁移管理。

- [ ] **步骤 1：安装 Alembic**

修改 `backend_python/requirements.txt`，在末尾追加：

```text
alembic==1.14.1
```

运行：`pip install alembic==1.14.1`
预期：安装成功，`alembic --version` 输出 1.14.1。

- [ ] **步骤 2：编写失败的迁移测试**

`backend_python/tests/unit/test_alembic_migrations.py`：

```python
"""基线迁移测试：upgrade head 建出全部既有表；downgrade base 全部删除。

使用程序化 Alembic API + 独立 SQLite 临时库，不触达开发 MySQL。
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "users", "refresh_tokens", "classes", "class_students",
    "assignments", "submissions", "ai_models", "ai_rules",
    "menus", "roles", "operation_logs",
}


def _make_config(db_path: Path) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def _table_names(db_path: Path) -> set:
    insp = inspect(create_engine(f"sqlite:///{db_path.as_posix()}"))
    return set(insp.get_table_names())


def test_upgrade_head_creates_all_existing_tables(tmp_path):
    db_path = tmp_path / "upgrade.db"
    command.upgrade(_make_config(db_path), "head")
    assert EXPECTED_TABLES <= _table_names(db_path)


def test_downgrade_base_drops_all_tables(tmp_path):
    db_path = tmp_path / "downgrade.db"
    cfg = _make_config(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(_table_names(db_path))
```

- [ ] **步骤 3：运行测试验证失败**

运行：`python -m pytest tests/unit/test_alembic_migrations.py -v`
预期：FAIL / ERROR，报错提示 `alembic.ini` 不存在。

- [ ] **步骤 4：初始化并配置 Alembic**

运行：

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review\backend_python"
alembic init alembic
```

然后清空 `alembic.ini` 中的占位 URL（URL 由 env.py 解析）：

```powershell
(Get-Content alembic.ini) -replace 'sqlalchemy.url = .*', 'sqlalchemy.url =' | Set-Content alembic.ini
```

用以下内容**整体替换** `backend_python/alembic/env.py`：

```python
"""Alembic 环境配置。

URL 解析优先级：ALEMBIC_DATABASE_URL 环境变量 > alembic.ini sqlalchemy.url > app settings。
- 日常命令（upgrade/stamp）：不设环境变量、ini 留空 → 用 settings.DATABASE_URL（开发 MySQL）。
- 生成基线/测试：用环境变量或 Config.set_main_option 指向临时 SQLite 库。
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base
from app import models  # noqa: F401  确保全部模型注册到 metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    return (
        os.environ.get("ALEMBIC_DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
        or settings.DATABASE_URL
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **步骤 5：生成基线迁移并人工核对**

对临时空 SQLite 库跑 autogenerate（生成的 create_table 取自模型 metadata，方言中立，可同时在 MySQL/SQLite 执行）：

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review\backend_python"
$env:ALEMBIC_DATABASE_URL = "sqlite:///$((Get-Location).Path -replace '\\','/')/baseline_tmp.db"
alembic revision --autogenerate -m "baseline"
Remove-Item Env:\ALEMBIC_DATABASE_URL
Remove-Item baseline_tmp.db
```

打开生成的 `alembic/versions/<rev>_baseline.py` 人工核对：
- `upgrade()` 中恰好有 11 个 `op.create_table(...)`，表名与 `EXPECTED_TABLES` 一致（不含 `agent_chat_messages`）；
- `downgrade()` 中恰好有 11 个 `op.drop_table(...)`；
- 若出现 MySQL 专属 kwargs（如 `mysql_charset`）导致 SQLite 测试失败，将其从迁移文件中删除（方言中立要求）。

- [ ] **步骤 6：运行迁移测试验证通过**

运行：`python -m pytest tests/unit/test_alembic_migrations.py -v`
预期：2 个测试全部 PASS。

- [ ] **步骤 7：开发库打基线标记**

开发 MySQL 库的表已存在，不执行 upgrade，只写版本标记：

```powershell
alembic stamp head
alembic current
```

预期：`alembic current` 输出刚生成的基线版本号。

- [ ] **步骤 8：Commit**

```powershell
git add backend_python/requirements.txt backend_python/alembic.ini backend_python/alembic backend_python/tests/unit
git commit -m "feat: 引入 Alembic 并建立数据库基线迁移"
```

说明（不写入代码）：`app/main.py` 的 `Base.metadata.create_all()` 本阶段保留——它幂等且向后兼容；MySQL 业务表后续变更一律通过 Alembic 迁移。开发 MySQL 中游离的旧 `agent_chat_messages` 表（数据已由任务 2 步骤 7 的脚本复制到 PG）在阶段 1 用独立 Alembic 迁移删除。

---

## 任务 4：Agent 结构化契约

对应规格第 10 节。本阶段先落地基础契约；`IntentDecision`、`ActionDraft`、`GradingDraft` 等属后续阶段。`UsageSummary` 与错误码常量先行定义，消费方（agent_runs 落库、SSE 新协议）在阶段 1 接入；本阶段任务 7 的 service 层使用 `SAFE_CHAT_ERROR_MESSAGE`。

**文件：**
- 创建：`backend_python/app/agent/contracts.py`
- 创建：`backend_python/tests/unit/agent/__init__.py`（空文件）
- 测试：`backend_python/tests/unit/agent/test_contracts.py`

- [ ] **步骤 1：编写失败的测试**

`backend_python/tests/unit/agent/test_contracts.py`：

```python
"""Agent 契约测试：身份上下文、模型档位、用量、稳定错误码。"""
import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    AGENT_BUDGET_EXCEEDED,
    AGENT_CHAT_ERROR,
    AGENT_MODEL_TIMEOUT,
    SAFE_CHAT_ERROR_MESSAGE,
    ActorContext,
    AgentError,
    ModelProfile,
    UsageSummary,
)


def test_actor_context_valid():
    ctx = ActorContext(user_id=1, role="teacher", request_id="req-1", session_id="sess-1")
    assert ctx.user_id == 1
    assert ctx.role == "teacher"


@pytest.mark.parametrize("role", ["admin", "root", "", "TEACHER"])
def test_actor_context_rejects_invalid_role(role):
    with pytest.raises(ValidationError):
        ActorContext(user_id=1, role=role, request_id="r", session_id="s")


def test_model_profile_values():
    assert {p.value for p in ModelProfile} == {"router", "general", "vision_grader", "reviewer"}


def test_usage_summary_total_tokens():
    usage = UsageSummary(model_id=1, profile=ModelProfile.GENERAL, prompt_tokens=100, completion_tokens=50)
    assert usage.total_tokens == 150
    assert usage.latency_ms == 0


def test_agent_error_defaults_not_retryable():
    err = AgentError(code=AGENT_CHAT_ERROR, message=SAFE_CHAT_ERROR_MESSAGE)
    assert err.retryable is False


def test_error_codes_stable():
    """错误码字符串是对外协议的一部分，改动必须显式审查。"""
    assert AGENT_CHAT_ERROR == "AGENT_CHAT_ERROR"
    assert AGENT_MODEL_TIMEOUT == "AGENT_MODEL_TIMEOUT"
    assert AGENT_BUDGET_EXCEEDED == "AGENT_BUDGET_EXCEEDED"
    assert SAFE_CHAT_ERROR_MESSAGE == "AI 服务暂时不可用，请稍后重试"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest tests/unit/agent/test_contracts.py -v`
预期：collection ERROR，`ModuleNotFoundError: No module named 'app.agent.contracts'`。

- [ ] **步骤 3：实现契约**

`backend_python/app/agent/contracts.py`：

```python
"""多智能体平台的结构化契约（规格文档第 10 节）。

跨 Agent / 工具 / 网关传递的关键状态必须使用这里的类型，
禁止靠自然语言拼接传递。所有跨阶段产物须带 schema_version（后续阶段补充）。
"""
from enum import Enum
from typing import Literal

from pydantic import BaseModel

ActorRole = Literal["teacher", "student", "superadmin"]


class ModelProfile(str, Enum):
    """模型能力档位（规格 11.2）。初期允许映射到同一物理模型，代码与数据保持档位隔离。"""
    ROUTER = "router"
    GENERAL = "general"
    VISION_GRADER = "vision_grader"
    REVIEWER = "reviewer"


class ActorContext(BaseModel):
    """服务端身份上下文（规格 10.1）。

    由认证依赖创建，绝不出现在 LLM 工具参数 Schema 中——
    LLM 既看不到也改不了这里的身份字段。
    """
    user_id: int
    role: ActorRole
    request_id: str
    session_id: str


class AgentError(BaseModel):
    """稳定的安全错误（规格 15.1）：code 供程序处理，message 面向用户。"""
    code: str
    message: str
    retryable: bool = False


class UsageSummary(BaseModel):
    """单次/单轮模型调用用量（规格 17.1）。阶段 1 由 agent_runs 落库。"""
    model_id: int
    profile: ModelProfile
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# ---- 稳定错误码（规格 13.2 / 15.1）：SSE 与 API 对外只暴露这些 ----
AGENT_CHAT_ERROR = "AGENT_CHAT_ERROR"
AGENT_MODEL_TIMEOUT = "AGENT_MODEL_TIMEOUT"
AGENT_BUDGET_EXCEEDED = "AGENT_BUDGET_EXCEEDED"

# 兜底安全消息：绝不携带异常类型与内部细节
SAFE_CHAT_ERROR_MESSAGE = "AI 服务暂时不可用，请稍后重试"
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m pytest tests/unit/agent/test_contracts.py -v`
预期：全部 PASS（7 项）。

- [ ] **步骤 5：Commit**

```powershell
git add backend_python/app/agent/contracts.py backend_python/tests/unit/agent
git commit -m "feat: 定义多智能体平台 Pydantic 基础契约"
```

---

## 任务 5：Prompt 版本注册表

对应规格 11.3。把现有 `agent.py` 的 `SYSTEM_PROMPT` 逐字迁移为 `teacher_assistant:v1`，内容不得有任何改动（行为不回退）。

**文件：**
- 创建：`backend_python/app/agent/prompts/__init__.py`
- 创建：`backend_python/app/agent/prompts/registry.py`
- 创建：`backend_python/app/agent/prompts/teacher_assistant.py`
- 测试：`backend_python/tests/unit/agent/test_prompt_registry.py`

- [ ] **步骤 1：编写失败的测试**

`backend_python/tests/unit/agent/test_prompt_registry.py`：

```python
"""Prompt 注册表测试：版本化注册、获取、冲突与缺失处理。"""
import pytest

from app.agent.prompts import get_prompt
from app.agent.prompts.registry import PromptTemplate, register_prompt
from app.agent.prompts.teacher_assistant import TEACHER_ASSISTANT_V1


def test_teacher_assistant_v1_registered_on_import():
    prompt = get_prompt("teacher_assistant")
    assert prompt is TEACHER_ASSISTANT_V1
    assert prompt.version == "v1"
    assert "教学助手" in prompt.content
    assert "绝不能出现" in prompt.content  # 原 SYSTEM_PROMPT 的 ID 保密规则


def test_get_prompt_by_explicit_version():
    assert get_prompt("teacher_assistant", "v1") is TEACHER_ASSISTANT_V1


def test_unknown_prompt_name_raises():
    with pytest.raises(KeyError):
        get_prompt("nonexistent_prompt")


def test_unknown_version_raises():
    with pytest.raises(KeyError):
        get_prompt("teacher_assistant", "v99")


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError):
        register_prompt(PromptTemplate(name="teacher_assistant", version="v1", content="x"))


def test_unspecified_version_returns_latest_registered():
    register_prompt(PromptTemplate(name="tmp_registry_probe", version="v1", content="一"))
    register_prompt(PromptTemplate(name="tmp_registry_probe", version="v2", content="二"))
    assert get_prompt("tmp_registry_probe").content == "二"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest tests/unit/agent/test_prompt_registry.py -v`
预期：collection ERROR，`ModuleNotFoundError: No module named 'app.agent.prompts'`。

- [ ] **步骤 3：实现注册表与教师助手 Prompt**

`backend_python/app/agent/prompts/registry.py`：

```python
"""Prompt 版本注册表（规格 11.3）。

系统 Prompt 以代码文件管理并带显式版本（如 teacher_assistant:v1）；
教师创建的 AiRule.prompt 是业务评分规则，不经过本注册表；
核心安全 Prompt 不允许在生产界面直接编辑。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    content: str


_REGISTRY: dict[str, dict[str, PromptTemplate]] = {}


def register_prompt(prompt: PromptTemplate) -> PromptTemplate:
    """注册 Prompt；同名同版本重复注册视为配置错误，直接拒绝。"""
    versions = _REGISTRY.setdefault(prompt.name, {})
    if prompt.version in versions:
        raise ValueError(f"Prompt 已注册: {prompt.name}:{prompt.version}")
    versions[prompt.version] = prompt
    return prompt


def get_prompt(name: str, version: str | None = None) -> PromptTemplate:
    """获取 Prompt；version 为 None 时返回最后注册的版本（dict 保序）。"""
    versions = _REGISTRY.get(name)
    if not versions:
        raise KeyError(f"未注册的 Prompt: {name}")
    if version is None:
        return list(versions.values())[-1]
    try:
        return versions[version]
    except KeyError:
        raise KeyError(f"Prompt {name} 没有版本 {version}") from None
```

`backend_python/app/agent/prompts/teacher_assistant.py`（content 必须与现有 `agent.py` 的 `SYSTEM_PROMPT` **逐字一致**）：

```python
"""教师助手系统 Prompt — 自 app.agent.agent 迁移，内容保持逐字不变。"""
from .registry import PromptTemplate, register_prompt

TEACHER_ASSISTANT_V1 = register_prompt(PromptTemplate(
    name="teacher_assistant",
    version="v1",
    content="""你是教学助手AI，服务于教师用户，通过工具查询数据库中的教学数据。
能力：查班级/班级学生、作业/提交情况、按姓名或学号查学生成绩、教师看板统计、待批改列表。

规则：
- 工具返回结果里的ID只是给你自己串联查询用的（先按名称/标题查列表拿到ID，再用ID查详情），最终回答里绝不能出现"ID:5"这类内容，用名称代替
- 不编造数据；工具查不到就如实说，并提示老师换个关键词
- 涉及学生信息注意隐私，不暴露密码等敏感字段
- 超出工具能力范围的请求（发通知、改数据等），如实告知做不到，不要假装完成

格式：
- 展示在窄悬浮面板里，不用emoji装饰标题
- 多条记录、字段整齐时用markdown表格；单条简单结果一两句话说完，不用硬套格式
- 同一个数字不要又列表/表格说一遍、又用文字重复统计一遍
- 别习惯性用"需要我帮您...吗？"结尾，除非接下来的操作明显有用
- 标题#、列表-/*后面要带空格，否则前端渲染不出来
""",
))
```

`backend_python/app/agent/prompts/__init__.py`：

```python
from .registry import PromptTemplate, get_prompt, register_prompt
from . import teacher_assistant  # noqa: F401  导入即注册

__all__ = ["PromptTemplate", "get_prompt", "register_prompt"]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m pytest tests/unit/agent/test_prompt_registry.py -v`
预期：全部 PASS（6 项）。

- [ ] **步骤 5：Commit**

```powershell
git add backend_python/app/agent/prompts backend_python/tests/unit/agent/test_prompt_registry.py
git commit -m "feat: 建立 Prompt 版本注册表并迁移教师助手系统 Prompt"
```

---

## 任务 6：统一模型网关 ModelGateway

对应规格 11.1/11.2。缓存键 `(profile, model_id, model_updated_at, prompt_version)`；管理员改配置后 `updated_at` 变化即整体失效，取代旧的 60s TTL。

**文件：**
- 创建：`backend_python/app/agent/services/__init__.py`
- 创建：`backend_python/app/agent/services/model_gateway.py`
- 测试：`backend_python/tests/unit/agent/test_model_gateway.py`

- [ ] **步骤 1：编写失败的测试**

`backend_python/tests/unit/agent/test_model_gateway.py`：

```python
"""ModelGateway 测试：默认配置解析、多维缓存键、档位参数、密钥脱敏。

init_chat_model 只构造 ChatOpenAI 客户端对象，不发起网络请求，可安全断言。
"""
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.agent.contracts import ModelProfile
from app.agent.services.model_gateway import ModelGateway, mask_secret
from app.core.exceptions import BizException
from app.models import AiModel


def test_raises_when_no_model_configured(db):
    gw = ModelGateway()
    with pytest.raises(BizException) as exc_info:
        gw.get_default_config(db)
    assert exc_info.value.code == 10016
    assert "没有可用的 AI 模型" in exc_info.value.message


def test_raises_when_default_model_has_no_api_key(db, ai_model_factory):
    ai_model_factory(api_key="")
    gw = ModelGateway()
    with pytest.raises(BizException) as exc_info:
        gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert "未配置 API Key" in exc_info.value.message


def test_falls_back_to_active_model_when_no_default(db, ai_model_factory):
    m = ai_model_factory(is_default=False, status="active")
    gw = ModelGateway()
    assert gw.get_default_config(db).id == m.id


def test_prefers_default_over_other_active(db, ai_model_factory):
    ai_model_factory(code="m-plain", is_default=False)
    default = ai_model_factory(code="m-default", is_default=True)
    gw = ModelGateway()
    assert gw.get_default_config(db).id == default.id


def test_chat_model_cached_by_key(db, ai_model_factory):
    ai_model_factory()
    gw = ModelGateway()
    first = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    second = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert first is second


def test_cache_key_includes_profile(db, ai_model_factory):
    ai_model_factory()
    gw = ModelGateway()
    general = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    router = gw.get_chat_model(db, ModelProfile.ROUTER, prompt_version="v1")
    assert general is not router


def test_cache_invalidated_when_model_updated(db, ai_model_factory):
    m = ai_model_factory()
    gw = ModelGateway()
    first = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    # 模拟管理员更新配置：updated_at 前进 1 秒（server onupdate 为秒级精度）
    db.execute(
        update(AiModel)
        .where(AiModel.id == m.id)
        .values(updated_at=m.updated_at + timedelta(seconds=1))
    )
    db.commit()
    second = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert second is not first


def test_profile_temperature_settings(db, ai_model_factory):
    ai_model_factory()
    gw = ModelGateway()
    router_llm = gw.get_chat_model(db, ModelProfile.ROUTER, prompt_version="v1")
    general_llm = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert router_llm.temperature == 0.1
    assert general_llm.temperature == 0.3
    assert general_llm.max_tokens == 2000


def test_mask_secret():
    assert mask_secret("sk-1234567890abcd") == "sk-1****abcd"
    assert mask_secret("short") == "****"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest tests/unit/agent/test_model_gateway.py -v`
预期：collection ERROR，`ModuleNotFoundError: No module named 'app.agent.services'`。

- [ ] **步骤 3：实现模型网关**

`backend_python/app/agent/services/model_gateway.py`：

```python
"""统一模型网关（规格 11.1/11.2）。

职责：从 AiModel 读取激活配置；按能力档位创建并缓存 LangChain ChatModel；
应用温度/超时/输出上限；密钥脱敏。缓存键：
(agent_profile, model_id, model_updated_at, prompt_version)
——管理员修改默认模型配置后 updated_at 变化，缓存立即失效，无需 TTL。
"""
import logging
import threading

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from ...core.exceptions import BizException
from ...models import AiModel
from ..contracts import ModelProfile

logger = logging.getLogger(__name__)

MODEL_NOT_CONFIGURED_CODE = 10016

# 能力档位参数（规格 11.2）：初期共用默认物理模型，参数按档位隔离
PROFILE_SETTINGS: dict[ModelProfile, dict] = {
    ModelProfile.ROUTER: {"temperature": 0.1, "max_tokens": 500, "timeout": 15},
    ModelProfile.GENERAL: {"temperature": 0.3, "max_tokens": 2000, "timeout": 60},
    ModelProfile.VISION_GRADER: {"temperature": 0.2, "max_tokens": 4000, "timeout": 120},
    ModelProfile.REVIEWER: {"temperature": 0.1, "max_tokens": 2000, "timeout": 60},
}


def mask_secret(value: str | None) -> str:
    """密钥脱敏：保留首尾各 4 位；长度 <= 8 全掩码；空值返回空串。"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


class ModelGateway:
    """创建并缓存 ChatModel。线程安全（LangGraph 会在后台线程执行工具）。"""

    def __init__(self) -> None:
        self._cache: dict[tuple, BaseChatModel] = {}
        self._lock = threading.Lock()

    def get_default_config(self, db: Session) -> AiModel:
        """默认模型优先；无默认回退到任一 active 模型；无可用模型或无 Key 抛业务异常。"""
        config = db.query(AiModel).filter(AiModel.is_default == True).first()
        if not config:
            config = db.query(AiModel).filter(AiModel.status == "active").first()
        if not config:
            raise BizException(MODEL_NOT_CONFIGURED_CODE, "数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")
        if not (config.api_key or "").strip():
            raise BizException(MODEL_NOT_CONFIGURED_CODE, f"AI 模型「{config.name}」未配置 API Key")
        return config

    def build_cache_key(self, db: Session, profile: ModelProfile, prompt_version: str) -> tuple:
        """多维缓存键：(agent_profile, model_id, model_updated_at, prompt_version)。"""
        config = self.get_default_config(db)
        return (profile.value, config.id, config.updated_at, prompt_version)

    def get_chat_model(self, db: Session, profile: ModelProfile, prompt_version: str = "v1") -> BaseChatModel:
        config = self.get_default_config(db)
        key = (profile.value, config.id, config.updated_at, prompt_version)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            llm = init_chat_model(
                model=f"openai:{config.model_name}",
                api_key=config.api_key,
                base_url=config.base_url,
                **PROFILE_SETTINGS[profile],
            )
            # 淘汰同 profile 下配置过期的条目；不同 profile 允许共存
            stale = [k for k in self._cache if k[0] == profile.value and k != key]
            for k in stale:
                del self._cache[k]
            self._cache[key] = llm
            logger.info(
                "ChatModel 已创建: profile=%s model=%s api_key=%s",
                profile.value, config.model_name, mask_secret(config.api_key),
            )
            return llm

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


# 全局单例：进程内共享缓存
model_gateway = ModelGateway()
```

`backend_python/app/agent/services/__init__.py`：

```python
from .model_gateway import ModelGateway, mask_secret, model_gateway

__all__ = ["ModelGateway", "mask_secret", "model_gateway"]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`python -m pytest tests/unit/agent/test_model_gateway.py -v`
预期：全部 PASS（9 项）。

- [ ] **步骤 5：Commit**

```powershell
git add backend_python/app/agent/services backend_python/tests/unit/agent/test_model_gateway.py
git commit -m "feat: 实现统一模型网关（多维缓存键 + 能力档位 + 密钥脱敏）"
```

---

## 任务 7：会话 CRUD 下沉 + 对话编排服务

对应规格 3.2「路由层包含会话逻辑」与 6.1 分层职责。本任务后 `agent.py` 的模型创建走 ModelGateway、Prompt 走注册表；`chat_with_agent` 的流式过滤行为不变。会话数据的读写全部使用 PG 会话库（`AssistantSessionLocal`）；模型配置查询使用 MySQL 业务库（`SessionLocal`）——service 层是双库边界的唯一交汇点。

**文件：**
- 创建：`backend_python/app/crud/agent_chat.py`
- 创建：`backend_python/app/agent/service.py`
- 修改：`backend_python/app/agent/agent.py`（整体替换）
- 测试：`backend_python/tests/unit/agent/test_agent_chat_crud.py`
- 测试：`backend_python/tests/integration/__init__.py`、`tests/integration/agent/__init__.py`（空文件）、`tests/integration/agent/test_assistant_service.py`

- [ ] **步骤 1：编写失败的 CRUD 测试**

`backend_python/tests/unit/agent/test_agent_chat_crud.py`：

```python
"""会话消息 CRUD 测试：最近消息窗口、会话聚合、归属隔离、删除。"""
from datetime import datetime, timedelta

from app.crud import agent_chat as crud
from app.models import AgentChatMessage

BASE = datetime(2026, 7, 24, 10, 0, 0)


def _msg(assistant_db, teacher_id, session_id, role, content, seconds=0):
    """显式指定 created_at（server_default 为秒级精度，同秒排序不稳定）。"""
    m = AgentChatMessage(
        teacher_id=teacher_id, session_id=session_id,
        role=role, content=content,
        created_at=BASE + timedelta(seconds=seconds),
    )
    assistant_db.add(m)
    assistant_db.commit()
    return m


def test_get_recent_messages_chronological(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "user", "第一条", 1)
    _msg(assistant_db, teacher.id, "s1", "assistant", "第二条", 2)
    _msg(assistant_db, teacher.id, "s1", "user", "第三条", 3)
    history = crud.get_recent_messages(assistant_db, teacher.id, "s1", limit=10)
    assert [h["content"] for h in history] == ["第一条", "第二条", "第三条"]


def test_get_recent_messages_respects_limit(assistant_db, teacher):
    for i in range(12):
        _msg(assistant_db, teacher.id, "s1", "user", f"消息{i}", i)
    history = crud.get_recent_messages(assistant_db, teacher.id, "s1", limit=10)
    assert len(history) == 10
    assert history[0]["content"] == "消息2"
    assert history[-1]["content"] == "消息11"


def test_get_recent_messages_isolated_by_teacher_and_session(assistant_db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _msg(assistant_db, other.id, "s1", "user", "别的老师", 1)
    _msg(assistant_db, teacher.id, "s2", "user", "别的会话", 2)
    _msg(assistant_db, teacher.id, "s1", "user", "我的", 3)
    history = crud.get_recent_messages(assistant_db, teacher.id, "s1")
    assert [h["content"] for h in history] == ["我的"]


def test_save_exchange_writes_user_then_assistant(assistant_db, teacher):
    crud.save_exchange(assistant_db, teacher.id, "s2", "问题", "回答")
    rows = (
        assistant_db.query(AgentChatMessage)
        .filter_by(teacher_id=teacher.id, session_id="s2")
        .order_by(AgentChatMessage.id)
        .all()
    )
    assert [(r.role, r.content) for r in rows] == [("user", "问题"), ("assistant", "回答")]


def test_list_sessions_summary_and_order(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "user", "你好", 1)
    _msg(assistant_db, teacher.id, "s1", "assistant", "回答一", 2)
    _msg(assistant_db, teacher.id, "s2", "user", "另一个会话", 3)
    sessions = crud.list_sessions(assistant_db, teacher.id)
    assert [s["sessionId"] for s in sessions] == ["s2", "s1"]
    s1 = next(s for s in sessions if s["sessionId"] == "s1")
    assert s1["messageCount"] == 2
    assert s1["lastMessage"] == "回答一"
    assert s1["lastTime"] is not None


def test_list_sessions_truncates_long_last_message(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "assistant", "x" * 60, 1)
    sessions = crud.list_sessions(assistant_db, teacher.id)
    assert sessions[0]["lastMessage"] == "x" * 50 + "..."


def test_get_session_messages_chronological_with_camel_keys(assistant_db, teacher):
    _msg(assistant_db, teacher.id, "s1", "user", "问", 2)
    _msg(assistant_db, teacher.id, "s1", "assistant", "答", 1)
    messages = crud.get_session_messages(assistant_db, teacher.id, "s1")
    assert [(m["role"], m["content"]) for m in messages] == [("assistant", "答"), ("user", "问")]
    assert set(messages[0].keys()) == {"role", "content", "createdAt"}


def test_delete_session_only_removes_own_session(assistant_db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _msg(assistant_db, teacher.id, "s1", "user", "我的", 1)
    _msg(assistant_db, other.id, "s1", "user", "别人的", 2)
    deleted = crud.delete_session(assistant_db, teacher.id, "s1")
    assert deleted == 1
    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=other.id).count() == 1


def test_delete_all_sessions_only_own(assistant_db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _msg(assistant_db, teacher.id, "s1", "user", "a", 1)
    _msg(assistant_db, teacher.id, "s2", "user", "b", 2)
    _msg(assistant_db, other.id, "s1", "user", "c", 3)
    deleted = crud.delete_all_sessions(assistant_db, teacher.id)
    assert deleted == 2
    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=other.id).count() == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest tests/unit/agent/test_agent_chat_crud.py -v`
预期：collection ERROR，`ModuleNotFoundError: No module named 'app.crud.agent_chat'`。

- [ ] **步骤 3：实现会话 CRUD**

`backend_python/app/crud/agent_chat.py`（逻辑自 `routers/chat.py` 迁移，返回 dict 供薄路由直接使用）：

```python
"""教师助手会话消息的数据访问（薄路由、厚 CRUD 约定）。"""
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from ..models import AgentChatMessage


def get_recent_messages(db: Session, teacher_id: int, session_id: str, limit: int = 10) -> list[dict]:
    """最近 N 条消息，按时间正序返回 [{role, content}]，供 Agent 上下文使用。"""
    records = (
        assistant_db.query(AgentChatMessage)
        .filter(AgentChatMessage.teacher_id == teacher_id, AgentChatMessage.session_id == session_id)
        .order_by(AgentChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(records)]


def save_exchange(db: Session, teacher_id: int, session_id: str, user_message: str, assistant_message: str) -> None:
    """保存一轮问答（user + assistant 两条）。"""
    db.add(AgentChatMessage(teacher_id=teacher_id, session_id=session_id, role="user", content=user_message))
    db.add(AgentChatMessage(teacher_id=teacher_id, session_id=session_id, role="assistant", content=assistant_message))
    db.commit()


def list_sessions(db: Session, teacher_id: int) -> list[dict]:
    """会话列表：每个 session 的消息数、最后时间、最后一条消息（截断 50 字，camelCase 键）。"""
    LastMsg = aliased(AgentChatMessage)
    last_content = (
        db.query(LastMsg.content)
        .filter(LastMsg.teacher_id == teacher_id, LastMsg.session_id == AgentChatMessage.session_id)
        .order_by(LastMsg.created_at.desc())
        .limit(1)
        .correlate(AgentChatMessage)
        .as_scalar()
    )
    sessions = (
        db.query(
            AgentChatMessage.session_id,
            func.count(AgentChatMessage.id).label("message_count"),
            func.max(AgentChatMessage.created_at).label("last_time"),
            last_content.label("last_message"),
        )
        .filter(AgentChatMessage.teacher_id == teacher_id)
        .group_by(AgentChatMessage.session_id)
        .order_by(func.max(AgentChatMessage.created_at).desc())
        .all()
    )
    result = []
    for s in sessions:
        content = s.last_message or ""
        result.append({
            "sessionId": s.session_id,
            "messageCount": s.message_count,
            "lastTime": s.last_time.isoformat() if s.last_time else None,
            "lastMessage": (content[:50] + "...") if len(content) > 50 else content,
        })
    return result


def get_session_messages(db: Session, teacher_id: int, session_id: str) -> list[dict]:
    """某个会话的全部消息，按时间正序，camelCase 键。"""
    messages = (
        assistant_db.query(AgentChatMessage)
        .filter(AgentChatMessage.teacher_id == teacher_id, AgentChatMessage.session_id == session_id)
        .order_by(AgentChatMessage.created_at.asc())
        .all()
    )
    return [
        {
            "role": m.role,
            "content": m.content,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


def delete_session(db: Session, teacher_id: int, session_id: str) -> int:
    """删除指定会话的全部消息，返回删除条数。"""
    deleted = assistant_db.query(AgentChatMessage).filter(
        AgentChatMessage.teacher_id == teacher_id,
        AgentChatMessage.session_id == session_id,
    ).delete()
    db.commit()
    return deleted


def delete_all_sessions(db: Session, teacher_id: int) -> int:
    """清空当前教师的全部会话消息，返回删除条数。"""
    deleted = assistant_db.query(AgentChatMessage).filter(
        AgentChatMessage.teacher_id == teacher_id,
    ).delete()
    db.commit()
    return deleted
```

- [ ] **步骤 4：运行 CRUD 测试验证通过**

运行：`python -m pytest tests/unit/agent/test_agent_chat_crud.py -v`
预期：全部 PASS（9 项）。

- [ ] **步骤 5：编写失败的 service 测试**

创建空文件 `backend_python/tests/integration/__init__.py`、`backend_python/tests/integration/agent/__init__.py`。

`backend_python/tests/integration/agent/test_assistant_service.py`：

```python
"""对话编排服务测试：事件序列、落库时机、错误安全、兜底存储。"""
import pytest
from langchain_core.messages import AIMessageChunk

from app.agent.service import ChatStreamEvent, stream_chat_events
from app.core.exceptions import BizException
from app.crud import agent_chat as crud
from app.models import AgentChatMessage
from tests.fakes import FakeAgent


@pytest.fixture()
def patch_agent(monkeypatch):
    def _patch(agent):
        monkeypatch.setattr("app.agent.service._get_agent", lambda db: agent)
    return _patch


def _roles_of_saved(assistant_db, teacher_id, session_id):
    rows = (
        assistant_db.query(AgentChatMessage)
        .filter_by(teacher_id=teacher_id, session_id=session_id)
        .order_by(AgentChatMessage.id)
        .all()
    )
    return [(r.role, r.content) for r in rows]


def test_stream_success_emits_chunks_then_done_and_saves(assistant_db, teacher, patch_agent):
    patch_agent(FakeAgent(["数据如下", "：3 个班级"]))
    events = list(stream_chat_events(teacher.id, "我有几个班级", "sess0001"))
    assert [e.data for e in events if e.event is None] == ["数据如下", "：3 个班级"]
    assert events[-1] == ChatStreamEvent(event="done", data="[DONE]")
    assert _roles_of_saved(assistant_db, teacher.id, "sess0001") == [
        ("user", "我有几个班级"),
        ("assistant", "数据如下：3 个班级"),
    ]


def test_history_loaded_into_agent_input(assistant_db, teacher, patch_agent):
    crud.save_exchange(assistant_db, teacher.id, "sess0002", "之前的问题", "之前的回答")
    agent = FakeAgent(["好的"])
    patch_agent(agent)
    list(stream_chat_events(teacher.id, "新问题", "sess0002"))
    messages = agent.received_input["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "之前的问题"),
        ("assistant", "之前的回答"),
        ("user", "新问题"),
    ]


def test_biz_exception_passes_safe_message(assistant_db, teacher, monkeypatch):
    def _raise(db_):
        raise BizException(10016, "数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")
    monkeypatch.setattr("app.agent.service._get_agent", _raise)
    events = list(stream_chat_events(teacher.id, "hi", "sess0003"))
    assert events == [ChatStreamEvent(event="error", data="数据库中没有可用的 AI 模型，请先在系统中配置 AI 模型")]
    assert assistant_db.query(AgentChatMessage).count() == 0


def test_unknown_error_hides_internals(assistant_db, teacher, patch_agent):
    patch_agent(FakeAgent(error=RuntimeError("pymysql: Packet sequence number wrong")))
    events = list(stream_chat_events(teacher.id, "hi", "sess0004"))
    errors = [e for e in events if e.event == "error"]
    assert len(errors) == 1
    assert errors[0].data == "AI 服务暂时不可用，请稍后重试"
    assert "Packet" not in errors[0].data
    assert "RuntimeError" not in errors[0].data


def test_partial_answer_saved_when_stream_breaks(assistant_db, teacher, patch_agent):
    class BrokenAgent:
        def stream(self, input, context=None, stream_mode=None):
            yield (AIMessageChunk(content="半截回答"), {})
            raise ConnectionError("reset by peer")

    patch_agent(BrokenAgent())
    events = list(stream_chat_events(teacher.id, "hi", "sess0005"))
    assert [e.data for e in events if e.event is None] == ["半截回答"]
    assert any(e.event == "error" for e in events)
    assert _roles_of_saved(assistant_db, teacher.id, "sess0005") == [
        ("user", "hi"),
        ("assistant", "半截回答"),
    ]
```

- [ ] **步骤 6：运行测试验证失败**

运行：`python -m pytest tests/integration/agent/test_assistant_service.py -v`
预期：collection ERROR，`ModuleNotFoundError: No module named 'app.agent.service'`。

- [ ] **步骤 7：实现 service 并改造 agent.py**

`backend_python/app/agent/service.py`：

```python
"""教师助手对话编排服务：读历史 → Agent 流式执行 → 落库 → 发事件。

路由层只做参数校验与 SSE 封装（薄路由约定）。本服务是双库边界的唯一交汇点：
- 会话历史与消息读写 → PostgreSQL 会话库（AssistantSessionLocal，委托 crud.agent_chat）
- 模型配置查询与 Agent 构建 → MySQL 业务库（SessionLocal，经 agent._get_agent → ModelGateway）
"""
import logging
from collections.abc import Iterator
from dataclasses import dataclass

from ..assistant_database import AssistantSessionLocal
from ..core.exceptions import BizException
from ..crud import agent_chat as agent_chat_crud
from ..database import SessionLocal
from .agent import _get_agent, chat_with_agent
from .contracts import SAFE_CHAT_ERROR_MESSAGE

logger = logging.getLogger(__name__)


@dataclass
class ChatStreamEvent:
    """SSE 事件。event=None 表示默认 message 事件（不带 event 字段，保持旧前端格式兼容）。"""
    event: str | None
    data: str


def stream_chat_events(teacher_id: int, message: str, session_id: str) -> Iterator[ChatStreamEvent]:
    full_answer = ""
    saved = False
    try:
        # 短事务读历史（PG 会话库）+ 构建 agent（MySQL 业务库查模型配置）：
        # LLM 客户端是独立 httpx 连接，不依赖 db session；
        # SSE 流式生成可能耗时 30s+，不能让请求在此其间持有连接池连接。
        with AssistantSessionLocal() as sdb:
            chat_history = agent_chat_crud.get_recent_messages(sdb, teacher_id, session_id)
        with SessionLocal() as db:
            agent = _get_agent(db)

        for content in chat_with_agent(agent, teacher_id, message, chat_history):
            full_answer += content
            yield ChatStreamEvent(event=None, data=content)

        # 流正常结束：先落库再发 done，保证前端收到 done 时数据已入库
        if full_answer:
            with AssistantSessionLocal() as sdb:
                agent_chat_crud.save_exchange(sdb, teacher_id, session_id, message, full_answer)
            saved = True
        yield ChatStreamEvent(event="done", data="[DONE]")
    except BizException as e:
        # 业务异常的 message 本身面向用户（如"未配置 AI 模型"），可直接透传
        logger.warning("Assistant biz error: code=%s message=%s", e.code, e.message)
        yield ChatStreamEvent(event="error", data=e.message)
    except Exception:
        # 兜底异常绝不外泄类型与细节（可能含内部实现与敏感信息，规格 3.2/15）
        logger.error("Agent chat error", exc_info=True)
        yield ChatStreamEvent(event="error", data=SAFE_CHAT_ERROR_MESSAGE)
    finally:
        # 异常中断时用独立 session 兜底存储（正常流程已存过则跳过）
        if full_answer and not saved:
            try:
                with AssistantSessionLocal() as sdb:
                    agent_chat_crud.save_exchange(sdb, teacher_id, session_id, message, full_answer)
            except Exception:
                logger.error("助手消息兜底存储失败", exc_info=True)
```

**整体替换** `backend_python/app/agent/agent.py`（对外函数签名不变；删除本地 SYSTEM_PROMPT 与 TTL 缓存）：

```python
"""LangChain 1.0 教师助手 Agent — 模型创建与 Prompt 统一走 ModelGateway / PromptRegistry"""
from sqlalchemy.orm import Session
from langchain_core.messages import AIMessageChunk
from langchain.agents import create_agent

from .contracts import ModelProfile
from .prompts import get_prompt
from .services.model_gateway import model_gateway
from .tools import ALL_TOOLS, TeacherContext   # TeacherContext 从 tools.py 里定义的地方导入

# agent 进程级缓存：key = (profile, model_id, model_updated_at, prompt_version)
# 管理员修改默认模型配置或 Prompt 发版后 key 变化，旧 agent 自动淘汰（取代旧的 60s TTL）
_agent_cache: dict = {}


def _build_messages(message: str, chat_history: list = None) -> list:
    """构建消息列表"""
    messages = []
    if chat_history:
        for msg in chat_history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"role": "user" if role == "user" else "assistant", "content": content})
    messages.append({"role": "user", "content": message})
    return messages


def _get_agent(db: Session):
    """获取教师助手 agent（进程级缓存）。

    ChatModel 由 ModelGateway 创建（统一温度/超时/输出上限/缓存），
    系统 Prompt 由 PromptRegistry 提供（当前版本 teacher_assistant:v1）。
    """
    prompt = get_prompt("teacher_assistant")
    cache_key = model_gateway.build_cache_key(db, ModelProfile.GENERAL, prompt.version)
    agent = _agent_cache.get(cache_key)
    if agent is None:
        llm = model_gateway.get_chat_model(db, ModelProfile.GENERAL, prompt_version=prompt.version)
        _agent_cache.clear()   # 同一时刻只有一个 (默认模型, prompt版本) 组合生效
        agent = create_agent(
            model=llm,
            tools=ALL_TOOLS,
            system_prompt=prompt.content,
            context_schema=TeacherContext,
        )
        _agent_cache[cache_key] = agent
    return agent


def chat_with_assistant(db: Session, teacher_id: int, message: str, chat_history: list = None):
    """流式输出 — 只 yield 大模型最终生成的纯文本，过滤掉工具调用分片和工具原始返回结果"""
    agent = _get_agent(db)
    yield from chat_with_agent(agent, teacher_id, message, chat_history)


def chat_with_agent(agent, teacher_id: int, message: str, chat_history: list = None):
    """流式输出 — 使用预构建的 agent，不持有 db session。

    适用于 SSE 长连接场景：调用方先用短事务构建 agent，
    再用本函数流式输出，避免长时间占用连接池连接。
    """
    messages = _build_messages(message, chat_history)

    for token, metadata in agent.stream(
        {"messages": messages},
        context=TeacherContext(teacher_id=teacher_id),   # ← 权限边界从这里传入，LLM 看不到
        stream_mode="messages",
    ):
        # 只处理 AIMessageChunk：ToolMessage 与工具调用分片不会泄露到前端
        if isinstance(token, AIMessageChunk) and token.text:
            yield token.text


def chat_with_assistant_sync(db: Session, teacher_id: int, message: str, chat_history: list = None) -> str:
    """同步版本 — 一次性返回完整回复"""
    agent = _get_agent(db)
    messages = _build_messages(message, chat_history)

    result = agent.invoke(
        {"messages": messages},
        context=TeacherContext(teacher_id=teacher_id),
    )
    ai_messages = [m for m in result["messages"] if m.type == "ai"]
    return ai_messages[-1].content if ai_messages else "抱歉，我无法处理您的请求。"
```

- [ ] **步骤 8：运行全部测试验证通过**

运行：`python -m pytest tests -v`
预期：既有全部测试 + 新增 5 项 service 测试全部 PASS。

- [ ] **步骤 9：Commit**

```powershell
git add backend_python/app/crud/agent_chat.py backend_python/app/agent/service.py backend_python/app/agent/agent.py backend_python/tests/unit/agent/test_agent_chat_crud.py backend_python/tests/integration
git commit -m "refactor: 助手会话逻辑下沉 CRUD/Service 层，Agent 接入模型网关与 Prompt 注册表"
```

---

## 任务 8：路由薄层化 + 角色校验 + SSE 错误安全

对应规格 3.2「聊天路由只校验登录」「SSE 返回底层异常」两项修复。外部协议保持旧格式：正文分片只有 `data:` 行、`event: done`、`event: error`（data 为安全文本）。

**文件：**
- 修改：`backend_python/app/routers/chat.py`（整体替换）
- 测试：`backend_python/tests/integration/agent/test_chat_api.py`

- [ ] **步骤 1：编写失败的 API 测试**

`backend_python/tests/integration/agent/test_chat_api.py`：

```python
"""教师助手 API 集成测试：角色权限、SSE 旧格式兼容、错误安全、会话隔离。"""
import pytest

from app.models import AgentChatMessage
from tests.fakes import FakeAgent

CHAT_URL = "/api/teacher/assistant/chat/stream"
SESSIONS_URL = "/api/teacher/assistant/sessions"
VALID_SESSION = "sess0001"


@pytest.fixture()
def patch_agent(monkeypatch):
    def _patch(agent):
        monkeypatch.setattr("app.agent.service._get_agent", lambda db: agent)
    return _patch


# ---------- 权限 ----------

def test_chat_requires_authentication(client):
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION})
    assert resp.status_code == 401


def test_chat_forbidden_for_student(client, student, auth_header):
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION}, headers=auth_header(student))
    assert resp.status_code == 403
    assert resp.json()["code"] == 10007


def test_chat_forbidden_for_admin(client, user_factory, auth_header):
    admin = user_factory("admin_root", "superadmin")
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION}, headers=auth_header(admin))
    assert resp.status_code == 403


def test_session_apis_forbidden_for_student(client, student, auth_header):
    headers = auth_header(student)
    assert client.get(SESSIONS_URL, headers=headers).status_code == 403
    assert client.get(f"{SESSIONS_URL}/s1/messages", headers=headers).status_code == 403
    assert client.delete(f"{SESSIONS_URL}/all", headers=headers).status_code == 403
    assert client.delete(f"{SESSIONS_URL}/s1", headers=headers).status_code == 403


# ---------- 参数校验 ----------

def test_chat_rejects_invalid_session_id(client, teacher, auth_header):
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": "bad!"}, headers=auth_header(teacher))
    assert resp.status_code == 400
    assert resp.json()["code"] == 10011


# ---------- SSE 旧格式兼容 ----------

def test_chat_stream_success_legacy_format(client, teacher, assistant_db, auth_header, patch_agent):
    patch_agent(FakeAgent(["你好", "，老师"]))
    resp = client.post(CHAT_URL, json={"message": "我有几个班级", "session_id": VALID_SESSION}, headers=auth_header(teacher))
    assert resp.status_code == 200
    assert "data: 你好" in resp.text
    assert "event: done" in resp.text
    assert "event: message" not in resp.text  # 旧格式：正文分片不带 event 字段
    rows = assistant_db.query(AgentChatMessage).filter_by(teacher_id=teacher.id, session_id=VALID_SESSION).all()
    assert len(rows) == 2


def test_chat_error_event_hides_internals(client, teacher, auth_header, patch_agent):
    patch_agent(FakeAgent(error=RuntimeError("pymysql: Packet sequence number wrong")))
    resp = client.post(CHAT_URL, json={"message": "hi", "session_id": VALID_SESSION}, headers=auth_header(teacher))
    assert "event: error" in resp.text
    assert "Packet sequence" not in resp.text
    assert "RuntimeError" not in resp.text


# ---------- 会话接口 ----------

def test_session_lifecycle(client, teacher, auth_header, patch_agent):
    patch_agent(FakeAgent(["回答内容"]))
    headers = auth_header(teacher)
    client.post(CHAT_URL, json={"message": "问题一", "session_id": VALID_SESSION}, headers=headers)

    resp = client.get(SESSIONS_URL, headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()["data"]["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["sessionId"] == VALID_SESSION
    assert sessions[0]["messageCount"] == 2

    resp = client.get(f"{SESSIONS_URL}/{VALID_SESSION}/messages", headers=headers)
    assert [m["role"] for m in resp.json()["data"]["messages"]] == ["user", "assistant"]

    resp = client.delete(f"{SESSIONS_URL}/{VALID_SESSION}", headers=headers)
    assert resp.status_code == 200
    resp = client.get(SESSIONS_URL, headers=headers)
    assert resp.json()["data"]["sessions"] == []


def test_sessions_isolated_between_teachers(client, teacher, user_factory, auth_header, patch_agent):
    patch_agent(FakeAgent(["回答"]))
    client.post(CHAT_URL, json={"message": "问题", "session_id": VALID_SESSION}, headers=auth_header(teacher))
    other = user_factory("t_other", "teacher")
    resp = client.get(SESSIONS_URL, headers=auth_header(other))
    assert resp.json()["data"]["sessions"] == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`python -m pytest tests/integration/agent/test_chat_api.py -v`
预期：至少以下失败——`test_chat_forbidden_for_student`（当前未校验角色，返回 200）、`test_chat_forbidden_for_admin`、`test_session_apis_forbidden_for_student`、`test_chat_error_event_hides_internals`（当前泄露 `RuntimeError: ...`）。

- [ ] **步骤 3：整体替换路由为薄层**

`backend_python/app/routers/chat.py`：

```python
"""教师助手路由（薄路由）：参数校验 + 依赖注入 + 委托 service / crud。"""
import logging
import re

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agent.service import stream_chat_events
from ..assistant_database import get_assistant_db
from ..core.exceptions import BadRequestException
from ..core.response import ok
from ..crud import agent_chat as agent_chat_crud
from ..deps import require_roles
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter()

# session_id 格式：8-64 位字母数字/下划线/连字符
# 前端用 Date.now().toString(36) + Math.random().toString(36) 生成，符合此格式
# 校验防止同一教师用任意字符串拼接历史，也避免特殊字符注入
_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


class ChatRequest(BaseModel):
    message: str
    session_id: str


@router.post("/teacher/assistant/chat/stream", response_class=EventSourceResponse)
def chat_stream(
    req: ChatRequest,
    teacher: User = Depends(require_roles("teacher")),
):
    if not _SESSION_ID_PATTERN.match(req.session_id):
        raise BadRequestException(10011, "session_id 格式非法，需为 8-64 位字母数字/下划线/连字符")
    for evt in stream_chat_events(teacher.id, req.message, req.session_id):
        kwargs = {"raw_data": evt.data}
        if evt.event:
            kwargs["event"] = evt.event
        yield ServerSentEvent(**kwargs)


@router.get("/teacher/assistant/sessions")
def get_sessions(
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """获取当前教师的会话列表 — 每个 session 返回最后一条消息和时间"""
    return ok({"sessions": agent_chat_crud.list_sessions(assistant_db, teacher.id)})


@router.get("/teacher/assistant/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """获取某个会话的全部消息 — 按时间正序排列"""
    return ok({
        "sessionId": session_id,
        "messages": agent_chat_crud.get_session_messages(assistant_db, teacher.id, session_id),
    })


@router.delete("/teacher/assistant/sessions/all")
def delete_all_sessions(
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """清空当前教师的全部会话消息"""
    deleted = agent_chat_crud.delete_all_sessions(assistant_db, teacher.id)
    return ok({"message": f"已清空全部会话，共{deleted}条消息"})


@router.delete("/teacher/assistant/sessions/{session_id}")
def delete_session(
    session_id: str,
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """删除指定会话的全部消息"""
    deleted = agent_chat_crud.delete_session(assistant_db, teacher.id, session_id)
    return ok({"message": f"已删除会话，共{deleted}条消息"})
```

- [ ] **步骤 4：运行全部测试验证通过**

运行：`python -m pytest tests -v`
预期：全部 PASS。

- [ ] **步骤 5：人工冒烟验证（行为不回退）**

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review\backend_python"
python -m uvicorn app.main:app --host 0.0.0.0 --port 83 --reload
```

前端 `npm run dev` 后打开教师端悬浮助手：发送一条查询（如"我有几个班级"），确认流式输出、会话列表、删除会话均与改造前一致；管理端切换默认模型后再次提问确认回答正常（缓存键失效生效）。

- [ ] **步骤 6：Commit**

```powershell
git add backend_python/app/routers/chat.py backend_python/tests/integration/agent/test_chat_api.py
git commit -m "fix: 助手接口补充教师角色校验，修复 SSE 错误信息泄露，路由薄层化"
```

---

## 任务 9：最终验证（verification-before-completion）

- [ ] **步骤 1：全量自动化验证**

```powershell
cd "d:\Pychrom Project\ai-smart-homework-review\backend_python"
python -m pytest tests -v
python -m compileall -q app
alembic current
```

预期：
- pytest 全绿（约 45 项）；
- compileall 无输出（语法通过）；
- `alembic current` 显示基线版本号。

- [ ] **步骤 2：对照阶段 0 完成标准**

| 规格要求 | 验证方式 |
|---|---|
| 聊天历史存 PostgreSQL 会话库（双库架构） | `tests/unit/test_assistant_database.py` + service/API 测试经 `AssistantSessionLocal` 落库断言 |
| 引入 Alembic 并建立基线（MySQL 业务库） | `tests/unit/test_alembic_migrations.py` + `alembic current` |
| 修正角色校验 | `test_chat_forbidden_for_student` / `test_chat_forbidden_for_admin` / `test_session_apis_forbidden_for_student` |
| 修正 SSE 错误泄露 | `test_chat_error_event_hides_internals` + `test_unknown_error_hides_internals` |
| 路由业务下沉 | `chat.py` 无查询/执行/落库代码；CRUD 与 service 测试覆盖 |
| Pydantic 契约 + 模型网关 + Prompt 版本 | 任务 4/5/6 测试 |
| pytest + 假模型 + 基础权限测试 | `tests/conftest.py`、`tests/fakes.py`、API 权限测试 |
| 现有教师查询能力通过新模型网关运行 | `agent.py` 的 `_get_agent` 经 `model_gateway.get_chat_model` |
| 兼容接口行为不回退 | `test_chat_stream_success_legacy_format`、`test_session_lifecycle` 及任务 8 步骤 5 人工冒烟 |

## 自检记录（编写时已执行）

**规格覆盖度：** 阶段 0 交付清单 6 项 + PG 会话库调整全部有对应任务（PG 双库→任务 2；Alembic→任务 3；契约/Prompt/网关→任务 4/5/6；pytest/假模型→任务 1/7；路由下沉→任务 7/8；角色校验/SSE/行为兼容→任务 8 + 人工冒烟）。阶段 1+ 的内容（结构化工具、多 Agent、新 SSE 协议、agent_sessions 等新表、PG 纳入 Alembic、MySQL 游离旧表删除）明确不在本计划。

**占位符扫描：** 无 TODO/待定；所有代码步骤均含完整实现。

**类型一致性：** `ChatStreamEvent(event: str | None, data: str)`（service 定义，路由与测试同用）；`FakeAgent(chunks, error)`（fakes.py 定义，service/API 测试同用）；夹具名 `db/client/teacher/student/auth_header/user_factory/ai_model_factory/patch_agent` 全计划统一；网关方法 `get_default_config/build_cache_key/get_chat_model/clear_cache` 与 `agent.py` 调用一致；crud 函数名与 `chat.py` 调用一致。
