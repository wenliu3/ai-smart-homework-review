# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project overview

AI-powered homework review system — **FastAPI + Vue 3 + LangChain** full-stack platform. Three roles: superadmin, teacher, student. Core capabilities: AI auto-grading, LangChain Agent teaching assistant (SSE streaming), dual-dimension plagiarism detection (text + image), class/assignment management.

See `AGENT.md` for detailed conventions, model list, and common task recipes.

## Dev commands

```bash
# Frontend (port 8080, proxies /api → localhost:83)
cd frontend && npm install && npm run dev

# Backend (port 83, API docs at /api/docs)
cd backend_python && pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 83 --reload

# Type-check frontend
cd frontend && npx vue-tsc --noEmit

# Syntax-check backend
python -m compileall -q backend_python/app

# Backend / frontend tests
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests -q
cd frontend && npm test

# Docker (frontend :80, backend :8000; data services bind localhost only)
docker compose --env-file .env.docker up -d
```

The repository has backend pytest and frontend Vitest suites. MySQL uses `backend_python/alembic/`; the assistant PostgreSQL database uses `backend_python/alembic_assistant/`. In Docker, only the backend service runs both migrations (`RUN_MIGRATIONS=1`) before seeding and starting Uvicorn; the Celery worker does not run migrations.

## Architecture

### Backend layers (strict separation)

```
routers/  →  crud/  →  models/
 (thin)      (thick)    (SQLAlchemy)
```

- **`routers/`** — only parameter extraction + `Depends()` + `return ok(crud.xxx())`. Never put business logic here.
- **`crud/`** — all business logic, queries, mutations. Returns dicts (not ORM objects).
- **`models/`** — SQLAlchemy models inheriting `Base, TimestampMixin, ModelMixin`. `ModelMixin.to_dict()` auto-converts snake_case columns → camelCase keys.
- **`schemas/`** — Pydantic request/response models.
- **`core/`** — `security.py` (JWT + bcrypt), `response.py` (`ok()` / `error()`), `exceptions.py` (`BizException` subclasses), `utils.py`.
- **`agent/`** — LangChain Agent. `agent.py` builds the agent + streams SSE; `tools.py` defines 7 query tools with `ToolRuntime` context injection for `teacher_id`. Each tool opens its own `SessionLocal()` to avoid thread-safety issues with pymysql.
- **`plagiarism/`** — Independent package. `__init__.py` exports `run_full_check()`. Text: char N-gram overlap + jieba TF-IDF cosine. Image: aHash/dHash + Hamming distance. `aggregator.py` merges dual-dimension results.

### Auth flow

1. `deps.py:get_current_user` — decodes Bearer JWT from header, loads User from DB, checks status.
2. `deps.py:require_roles(*roles)` — factory that chains after `get_current_user`, checks `user.role`.
3. Frontend `request.ts` interceptor handles 401 → refresh token → retry queue; 403 shows message without clearing login.

### Frontend structure

- `api/` — one file per backend route module, all using `@/utils/request` (axios wrapper).
- `router/index.ts` — static `constantRoutes`; `beforeEach` guard checks auth + role.
- `store/` — Vuex (not Pinia, despite Pinia being installed). Modules: `auth`, `app`, `user`, `dashboard`.
- `components/` — shared: `AssistantPanel.vue` (AI teaching assistant floating panel), `FloatingAssistantButton.vue`, `WangEditor.vue`, `PageHeader.vue`.
- `views/` — organized by role: `admin/`, `teacher/`, `student/`, `dashboard/`, `system/`.

Route convention: `/teacher/xxx`, `/student/xxx`, `/admin/xxx`, `/system/xxx`.

## Key patterns

### Response format
```python
return ok(data)           # → {"code": 200, "data": ..., "message": "操作成功"}
raise NotFoundException(10015, "作业不存在")  # → {"code": 10015, "message": "..."}
```

### camelCase / snake_case
DB columns are snake_case. Model `to_dict()` converts to camelCase for API responses. Frontend sends camelCase; CRUD layer uses `camel_to_snake()` from `core/utils.py` when processing request params.

### File uploads
Stored in `uploads/` (configurable via `UPLOAD_DIR`). Served at `/uploads/<filename>` (no `/api` prefix). Plagiarism temp files go to `uploads/plagiarism_tmp/`.

## Gotchas

- **Dual Alembic histories**: business schema changes go to `alembic/`; assistant runtime schema changes go to `alembic_assistant/`. Keep both at head in deployment.
- **Vuex, not Pinia**: Pinia is in `package.json` but unused. All state management is Vuex 4.
- **Thread safety in Agent tools**: each tool creates its own `SessionLocal()` session — do NOT pass the request's `db` session into agent tools. pymysql connections are not thread-safe and LangGraph runs tools in background threads.
- **SSE streaming**: `agent/agent.py:chat_with_agent()` yields only `AIMessageChunk.text` — filters out ToolMessage and tool-call chunks so raw tool results never leak to frontend.
- **Plagiarism module path**: migrated from `app.core.plagiarism` to `app.plagiarism`. Never import from the old path.
- **Git remote**: uses SSH (`git@github.com:wenliu3/ai-smart-homework-review.git`). HTTPS may fail due to network issues.
- **allow_attachments field**: `Boolean` (TINYINT(1)), not JSON — don't treat it as a JSON column.

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.Codex/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发，或在执行实现计划之前使用——通过原生工具或 git worktree 回退机制确保隔离工作区存在
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Codex / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
