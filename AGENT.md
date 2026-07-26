# Agent 上下文文件

> 本文件供 AI 编程助手快速理解项目结构、开发规范与关键约定。

## 项目概述

**AI 智能作业批改系统** — 基于 FastAPI + Vue 3 + LangChain 的全栈教学平台。
核心能力：AI 自动批改、智能教学助手（LangChain Agent）、文档查重（文本+图片双维度）、班级与作业管理。

- 仓库：`git@github.com:wenliu3/ai-smart-homework-review.git`（SSH）
- 后端端口：83，API 文档：`http://localhost:83/api/docs`
- 前端端口：8080（vite dev server，代理 `/api` → `localhost:83`）
- 数据库（双库架构）：
  - 业务库：MySQL `localhost:3306/ai_smart_review`
  - AI 会话库：PostgreSQL（`ASSISTANT_DATABASE_URL`，`app/assistant_database.py`），存放多智能体会话/运行/审批数据，由 `alembic_assistant/` 管理迁移

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite 3 + Element Plus + Tailwind CSS 4 + Vuex 4 |
| 后端 | FastAPI + SQLAlchemy 2.0 + PyMySQL + PyJWT + bcrypt |
| AI | LangChain 1.0 + LangGraph（Agent）+ 多模型接入（DeepSeek/通义千问/豆包）|
| 查重 | 字符 N-gram + TF-IDF 余弦相似度 + 感知哈希（aHash/dHash）|

## 开发命令

```bash
# 前端
cd frontend && npm install && npm run dev

# 后端
cd backend_python && pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 83 --reload

# 编译检查（验证后端语法）
python -m compileall -q backend_python/app

# 后端测试（双库均用 sqlite 替身，无需真实数据库）
cd backend_python && python -m pytest -q

# 前端类型检查 + 单元测试
cd frontend && npx vue-tsc --noEmit
cd frontend && npx vitest run
```

## 项目结构

```
backend_python/
├── app/
│   ├── main.py              # FastAPI 入口，注册路由 + 全局异常处理
│   ├── config.py            # 配置（环境变量/.env）
│   ├── database.py          # SQLAlchemy 引擎与会话
│   ├── deps.py              # 依赖注入（get_current_user / require_roles）
│   ├── core/
│   │   ├── security.py      # JWT 签发/校验 + bcrypt 密码哈希
│   │   ├── response.py      # 统一响应 ok() / error()
│   │   ├── exceptions.py    # BizException 异常体系
│   │   └── utils.py         # camel_to_snake / now 等工具
│   ├── models/              # SQLAlchemy 模型（见下方说明）
│   ├── schemas/             # Pydantic 请求/响应模型
│   ├── crud/                # 数据库操作层（业务逻辑在这里）
│   ├── routers/             # API 路由（仅转发，不含业务逻辑）
│   ├── plagiarism/          # 查重模块（独立包）
│   │   ├── config.py        # 查重参数（阈值/权重/N-gram 窗口）
│   │   ├── text.py          # 文本查重（N-gram + TF-IDF）
│   │   ├── image.py         # 图片查重（感知哈希）
│   │   ├── extractors.py    # 文件解析（docx/pdf/txt → 文本+图片）
│   │   ├── aggregator.py    # 双维度结果合并
│   │   └── __init__.py      # 统一入口 run_full_check()
│   ├── assistant_database.py # AI 会话库（PostgreSQL）引擎与会话
│   ├── tasks/               # Celery 任务（AI 批改异步执行）
│   └── agent/               # 多智能体运行时（LangGraph）
│       ├── service.py       # 编排入口 + SSE 流式输出（教师/学生/管理员三路径）
│       ├── runtime.py       # 运行时预算/取消控制
│       ├── gateway.py       # 统一模型网关（缓存 + 密钥脱敏）
│       ├── registry.py      # Prompt/Agent 注册表
│       ├── checkpointer.py  # LangGraph checkpoint（生产 PG / 测试内存）
│       ├── contracts.py     # 稳定错误码与事件契约
│       ├── graphs/          # 各角色 StateGraph（teacher/student/admin/grading/plagiarism/approval）
│       ├── supervisors/     # 角色主管节点
│       ├── subagents/       # 专业子智能体节点
│       └── tools/           # 角色查询工具集（每个工具独立 SessionLocal）
├── alembic/                 # 业务库（MySQL）迁移
├── alembic_assistant/       # AI 会话库（PostgreSQL）迁移
├── tests/                   # pytest（unit / integration / security / evals）
├── uploads/                 # 上传文件目录
├── requirements.txt
└── .env.example

frontend/
├── src/
│   ├── api/                 # API 服务层（每个文件对应一个后端路由模块）
│   ├── components/          # 公共组件
│   ├── views/               # 页面视图
│   │   ├── admin/           # 管理员页面
│   │   ├── teacher/         # 教师页面
│   │   ├── student/         # 学生页面
│   │   └── dashboard/       # 仪表盘
│   ├── router/index.ts      # 路由配置 + 权限守卫
│   ├── store/               # Vuex 状态管理
│   ├── types/               # TypeScript 类型定义
│   └── utils/request.ts     # Axios 封装
├── package.json
└── vite.config.ts
```

## 后端开发规范

### 路由 → CRUD 分层

路由层（`routers/`）只做参数接收和响应包装，业务逻辑全部在 `crud/` 层：

```python
# routers/assignments.py — 路由层（薄）
@router.get("/teacher/assignments/{id}")
def get_detail(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(assignment_crud.get_teacher_detail(db, id))

# crud/assignment.py — 业务层（厚）
def get_teacher_detail(db: Session, assignment_id: int) -> dict:
    ...
```

### 统一响应格式

```python
from app.core.response import ok
return ok(data)  # → {"code": 200, "data": ..., "message": "操作成功"}
```

### 异常处理

```python
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
raise NotFoundException(10015, "作业不存在")
raise BadRequestException(10011, "参数错误")
raise ForbiddenException(10007, "无权操作")
```

全局异常处理器在 `main.py` 中注册，自动将 `BizException` 转为 `{"code": ..., "message": ...}`。

### 认证与权限

```python
from app.deps import get_current_user, require_roles

# 需要登录
@router.get("/...")
def handler(current_user: User = Depends(get_current_user)):

# 需要特定角色
@router.post("/...")
def handler(current_user: User = Depends(require_roles("teacher", "superadmin"))):
```

角色：`superadmin` / `teacher` / `student`

### 命名转换

数据库字段用 `snake_case`，API 返回用 `camelCase`。模型基类 `ModelMixin.to_dict()` 自动转换。前端传参也用 `camelCase`，CRUD 层用 `camel_to_snake()` 转换。

### 文件上传

上传文件存储在 `uploads/` 目录，URL 格式 `/uploads/<filename>`。`settings.upload_path` 返回 Path 对象。

## 数据库模型

| 模型 | 表名 | 说明 |
|------|------|------|
| `User` | users | 用户（superadmin/teacher/student），password 为 bcrypt 哈希 |
| `Class` | classes | 班级，关联 teacher_id |
| `ClassStudent` | class_students | 班级-学生关联表 |
| `Assignment` | assignments | 作业，classes 字段为 JSON `[{id, name}]` |
| `Submission` | submissions | 学生提交，status: draft/submitted/ai_reviewed/teacher_reviewed |
| `AiModel` | ai_models | 大模型配置（name/api_key/base_url/model_type） |
| `AiRule` | ai_rules | AI 批改规则（prompt/max_score/model_type） |
| `Menu` | menus | 菜单（RBAC） |
| `Role` | roles | 角色 |
| `RefreshToken` | refresh_tokens | 刷新令牌 |
| `AgentActionExecution` | agent_action_executions | 审批动作执行幂等账本（MySQL 侧） |

**AI 会话库（PostgreSQL，`AssistantBase`）**：`AgentChatMessage`（旧版对话记录）、`AgentSession` / `AgentRun` / `AgentStep` / `AgentArtifact` / `AgentMessage`（多智能体运行时）、`AgentApproval`（人工审批）。批改任务会话 id 以 `grading-` 为前缀，属系统会话，不出现在用户会话列表、不可被聊天/取消接口操作。

模型基类：`TimestampMixin`（created_at/updated_at）+ `ModelMixin`（to_dict 方法）。

## 查重模块

入口函数 `run_full_check()` 在 `plagiarism/__init__.py`，支持文本+图片双维度。

### 算法

```
综合重复率 = 片段重合度 × 片段权重 + 主题相似度 × 主题权重
```

- **片段重合度**：字符级 10-gram 重叠系数（抓整句照抄）
- **主题相似度**：jieba 分词 + TF-IDF 余弦相似度（抓同义替换）

### 可调参数（`plagiarism/config.py`）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PASS_RATE` | 30 | 合格阈值(%) |
| `PHRASE_WEIGHT` | 0.6 | 片段重合度权重 |
| `TOPIC_WEIGHT` | 0.4 | 主题相似度权重 |
| `PHRASE_NGRAM` | 10 | N-gram 窗口长度 |
| `MIN_VALID_CHARS` | 40 | 最小有效字符数 |
| `MAX_SUBMISSIONS` | 200 | 单次查重上限 |

这些参数可通过 API 动态覆盖（前端参数设置弹窗），不传时使用默认值。

### 两个查重入口

1. **作业查重**：`POST /teacher/assignments/{id}/plagiarism`（Form 上传模板文件 + 可选参数）
2. **临时查重**：`POST /plagiarism/adhoc-check`（Form 上传多文件 + 模板 + 可选参数）

## 前端开发规范

### API 层

每个后端路由模块对应一个 `api/` 下的 ts 文件。使用 `@/utils/request` 封装的 axios。

```typescript
// api/assignments.ts
import request from "@/utils/request";
export function getAssignmentList(params) {
  return request({ url: "/teacher/assignments", method: "get", params });
}
```

### 类型定义

类型定义在 `types/` 目录。注意：`api/` 目录中的接口定义可能与 `types/` 有重复，修改时需同步。

### 路由与权限

路由配置在 `router/index.ts`，静态路由 `constantRoutes`。基于角色的路由守卫在 `router/index.ts` 的 `beforeEach` 中。

路径规范：`/teacher/xxx`、`/student/xxx`、`/admin/xxx`、`/system/xxx`

### 状态管理

使用 Vuex 4，store 模块在 `store/` 目录。主要模块：`user`（用户信息/token）、`app`（设备类型/侧边栏）。

## 常见开发任务

### 新增 API 接口

1. `routers/xxx.py` 添加路由函数，用 `Depends(get_current_user)` 或 `require_roles()` 鉴权
2. `crud/xxx.py` 添加业务函数
3. `frontend/src/api/xxx.ts` 添加 API 调用函数
4. 需要时在 `frontend/src/types/xxx.ts` 添加类型定义

### 新增数据库模型

1. `models/xxx.py` 定义模型类：业务库继承 `Base, TimestampMixin, ModelMixin`；AI 会话库继承 `AssistantBase`
2. `models/__init__.py` 注册导出
3. 开发期 `main.py` 的 `Base.metadata.create_all()` 会自动建业务表；正式迁移需补 alembic revision（业务库 `alembic/`，会话库 `alembic_assistant/`）

### 修改查重参数

后端 `plagiarism/config.py` 修改默认值。前端两个查重页面都有"参数设置"弹窗，支持运行时调整。

## 注意事项

- **不要**在路由层写业务逻辑，全部放 `crud/` 层
- **不要**在前端硬编码 API 路径前缀，统一通过 `api/` 层调用
- **密码**统一用 `core/security.py` 的 `hash_password()` 加密，不要明文存储
- **JSON 字段**（如 `classes`、`ai_rule`、`attachments`）在模型中是 Python list/dict，写入数据库自动序列化
- **camelCase/snake_case**转换通过 `core/utils.py` 的 `camel_to_snake()` 和模型的 `to_dict()` 自动处理
- **查重模块**已从 `core/` 迁移到独立的 `plagiarism/` 包，不要引用旧路径 `app.core.plagiarism`
- **allow_attachments** 字段是 `Boolean` 类型（非 JSON），数据库列类型为 `TINYINT(1)`
- **状态管理**使用 Vuex 4（Pinia 依赖已移除）
- **迁移**：业务库（MySQL）用 `alembic/`，AI 会话库（PostgreSQL）用 `alembic_assistant/`（`alembic -c alembic_assistant.ini`）；容器 entrypoint 在 `RUN_MIGRATIONS=1` 时自动执行，并对旧版 create_all 建出的既有库先 stamp 基线再 upgrade
- **双库边界**：业务数据只走 `SessionLocal`（MySQL），AI 会话数据只走 `AssistantSessionLocal`（PostgreSQL），交汇点在 `app/agent/service.py` 与 `crud/user.py` 的删除清理；不要在同一事务里混用两库
- **敏感配置**：`.env.docker` 已从 git 移除，复制 `.env.docker.example` 并改强密钥后使用
- Git 远程使用 **SSH 协议**（`git@github.com:...`），HTTPS 会被网络干扰
