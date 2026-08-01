# CI 回归恢复实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 定向撤销 `e723154` 对助手生产代码、测试和前端配置造成的破坏，保留该提交新增文档，并在稳定基线上完成全项目健康总览。

**架构：** PostgreSQL 多智能体运行时继续负责会话、运行、步骤、产物、审批和异步批改审计；MySQL `AgentChatMessage` 继续作为教师快捷聊天历史，两者本次不合并。恢复操作以 `e723154` 的父提交 `56ff806` 为已知文件基线，仅恢复该提交触碰的代码、测试和配置。

**技术栈：** FastAPI、SQLAlchemy、Alembic、LangChain/LangGraph、Vue 3、TypeScript、Vitest、Vite、GitHub Actions、Docker Compose

---

## 文件结构与职责

### 后端生产代码

- `backend_python/app/crud/agent_session.py`：PostgreSQL 助手会话和消息 CRUD。
- `backend_python/app/crud/agent_run.py`：运行、步骤、产物、取消、失败与原子收口 CRUD。
- `backend_python/app/routers/assistant.py`：多角色助手运行、会话、审批和产物 API。
- `backend_python/app/schemas/assistant.py`：助手 API 请求契约。
- `backend_python/app/routers/chat.py`：教师快捷聊天薄路由与教师角色边界。
- `backend_python/app/main.py`：注册助手路由。
- `backend_python/app/agent/runtime.py`：运行时预算和上下文边界。
- `backend_python/app/agent/tools/__init__.py`：结构化工具导出。

### 后端回归测试

- `backend_python/tests/integration/agent/test_agent_runtime_crud.py`
- `backend_python/tests/integration/agent/test_assistant_v2_api.py`
- `backend_python/tests/unit/agent/test_legacy_tools_delegate.py`
- `backend_python/tests/unit/agent/test_runtime_contracts.py`
- `backend_python/tests/unit/agent/test_specialist_registry.py`
- `backend_python/tests/unit/agent/test_teacher_graph.py`
- `backend_python/tests/unit/agent/test_teaching_query_tools.py`

### 前端生产代码与测试设施

- `frontend/src/api/assistant.ts`：运行、会话、审批、反馈、产物和 SSE 客户端契约。
- `frontend/vitest.config.ts`：Vue 插件、别名、jsdom 和样式依赖配置。
- `frontend/src/__tests__/setup.ts`：测试浏览器 API 初始化。
- `frontend/package.json`：测试脚本和直接依赖声明。
- `frontend/src/api/__tests__/assistant.spec.ts`：助手 API 与 SSE 回归测试。

### 审计输出

- `docs/reviews/2026-08-01-project-health-overview.md`：恢复后项目架构、质量、安全与运维风险总览。

---

### 任务 1：恢复后端助手运行时边界

**文件：**

- 恢复：`backend_python/app/agent/runtime.py`
- 恢复：`backend_python/app/agent/tools/__init__.py`
- 恢复：`backend_python/app/crud/agent_run.py`
- 恢复：`backend_python/app/crud/agent_session.py`
- 恢复：`backend_python/app/main.py`
- 恢复：`backend_python/app/routers/assistant.py`
- 恢复：`backend_python/app/routers/chat.py`
- 恢复：`backend_python/app/schemas/assistant.py`
- 恢复：`backend_python/tests/integration/agent/test_agent_runtime_crud.py`
- 恢复：`backend_python/tests/integration/agent/test_assistant_v2_api.py`
- 恢复：`backend_python/tests/unit/agent/test_legacy_tools_delegate.py`
- 恢复：`backend_python/tests/unit/agent/test_runtime_contracts.py`
- 恢复：`backend_python/tests/unit/agent/test_specialist_registry.py`
- 恢复：`backend_python/tests/unit/agent/test_teacher_graph.py`
- 恢复：`backend_python/tests/unit/agent/test_teaching_query_tools.py`

- [ ] **步骤 1：确认后端红灯由缺失会话 CRUD 触发**

运行：

```powershell
Set-Location backend_python
D:\miniforge\envs\scientific_research\python.exe -c "import app.main"
```

预期：退出码 1，根因包含 `ImportError: cannot import name 'agent_session' from 'app.crud'`。

- [ ] **步骤 2：机械恢复后端目标文件**

在仓库根目录运行以下精确路径恢复。该命令只反向应用 `e723154` 对列出文件的补丁，不触碰四份需保留的新增文档：

```powershell
$backendRecoveryPaths = @(
  'backend_python/app/agent/runtime.py',
  'backend_python/app/agent/tools/__init__.py',
  'backend_python/app/crud/agent_run.py',
  'backend_python/app/crud/agent_session.py',
  'backend_python/app/main.py',
  'backend_python/app/routers/assistant.py',
  'backend_python/app/routers/chat.py',
  'backend_python/app/schemas/assistant.py',
  'backend_python/tests/integration/agent/test_agent_runtime_crud.py',
  'backend_python/tests/integration/agent/test_assistant_v2_api.py',
  'backend_python/tests/unit/agent/test_legacy_tools_delegate.py',
  'backend_python/tests/unit/agent/test_runtime_contracts.py',
  'backend_python/tests/unit/agent/test_specialist_registry.py',
  'backend_python/tests/unit/agent/test_teacher_graph.py',
  'backend_python/tests/unit/agent/test_teaching_query_tools.py'
)
git diff 56ff806 e723154 -- $backendRecoveryPaths | git apply --reverse
```

- [ ] **步骤 3：验证后端恢复范围准确**

运行：

```powershell
git diff --name-status -- $backendRecoveryPaths
git diff --check -- $backendRecoveryPaths
rg -n "from \.\.crud import agent_session|from app\.crud\.agent_session" backend_python/app backend_python/tests
```

预期：名称列表仅含上方目标文件；`git diff --check` 无输出；所有 `agent_session` 引用均有恢复后的模块承接。

- [ ] **步骤 4：验证后端绿灯**

运行：

```powershell
Set-Location backend_python
D:\miniforge\envs\scientific_research\python.exe -c "import app.main; print('backend import ok')"
D:\miniforge\envs\scientific_research\python.exe -m compileall -q app
D:\miniforge\envs\scientific_research\python.exe -m pytest tests/integration/agent/test_agent_runtime_crud.py tests/integration/agent/test_assistant_v2_api.py tests/unit/agent/test_runtime_contracts.py tests/unit/agent/test_teacher_graph.py -q
```

预期：导入输出 `backend import ok`，语法检查退出码 0，所列测试全部通过。

- [ ] **步骤 5：提交后端恢复**

```powershell
git add -- $backendRecoveryPaths
git commit -m "fix: 恢复助手运行时持久化边界（任务 1/4）"
```

### 任务 2：恢复前端助手 API 与测试环境

**文件：**

- 恢复：`frontend/package.json`
- 恢复：`frontend/src/__tests__/setup.ts`
- 恢复：`frontend/src/api/__tests__/assistant.spec.ts`
- 恢复：`frontend/src/api/assistant.ts`
- 恢复：`frontend/vitest.config.ts`

- [ ] **步骤 1：确认前端测试与构建红灯**

运行：

```powershell
Set-Location frontend
npx vitest run src/store/modules/__tests__/user.spec.ts src/utils/__tests__/request.spec.ts
npm run build
```

预期：Vitest 因 `localStorage is not defined` 失败；构建因无法加载 `src/api/assistant` 失败。

- [ ] **步骤 2：机械恢复前端目标文件**

在仓库根目录运行：

```powershell
$frontendRecoveryPaths = @(
  'frontend/package.json',
  'frontend/src/__tests__/setup.ts',
  'frontend/src/api/__tests__/assistant.spec.ts',
  'frontend/src/api/assistant.ts',
  'frontend/vitest.config.ts'
)
git diff 56ff806 e723154 -- $frontendRecoveryPaths | git apply --reverse
```

- [ ] **步骤 3：重新执行干净依赖安装**

```powershell
Set-Location frontend
npm ci
npm ls --depth=0
```

预期：安装退出码 0；`dompurify`、`@vue/test-utils` 和 `jsdom` 不再标记为 extraneous。

- [ ] **步骤 4：验证前端绿灯**

```powershell
npx vitest run src/api/__tests__/assistant.spec.ts src/store/modules/__tests__/user.spec.ts src/utils/__tests__/request.spec.ts src/components/__tests__/AssistantPanel.spec.ts src/views/teacher/correcting/__tests__/GradingDimensionsPanel.spec.ts
npm run build
```

预期：所列测试全部通过；`vue-tsc --noEmit` 与 Vite 构建均退出码 0。

- [ ] **步骤 5：清理构建生成声明的非语义变更并提交**

确认 `frontend/auto-imports.d.ts` 与 `frontend/components.d.ts` 的工作树哈希和 `HEAD` blob 一致；若一致，用精确 `git add` 刷新索引，不提交空差异：

```powershell
git hash-object frontend/auto-imports.d.ts
git rev-parse HEAD:frontend/auto-imports.d.ts
git hash-object frontend/components.d.ts
git rev-parse HEAD:frontend/components.d.ts
git add -- frontend/auto-imports.d.ts frontend/components.d.ts
git add -- $frontendRecoveryPaths
git diff --cached --check
git commit -m "fix: 恢复助手 API 与测试环境（任务 2/4）"
```

### 任务 3：执行与 CI 等价的完整验证

**文件：**

- 验证：全部恢复文件
- 保持：四份 `2026-07-31` 新增设计与计划文档

- [ ] **步骤 1：运行后端完整 CI 命令**

```powershell
Set-Location backend_python
D:\miniforge\envs\scientific_research\python.exe -m compileall -q app
D:\miniforge\envs\scientific_research\python.exe -m pytest -q
```

预期：退出码 0，无收集错误或失败。

- [ ] **步骤 2：运行前端完整 CI 命令**

```powershell
Set-Location frontend
npx vitest run
npm run build
```

预期：退出码 0，无失败测试、类型错误或构建错误。

- [ ] **步骤 3：验证保留文档与悬空引用**

```powershell
Test-Path docs/superpowers/plans/2026-07-31-assistant-run-timeout.md
Test-Path docs/superpowers/plans/2026-07-31-student-experience-refresh.md
Test-Path docs/superpowers/specs/2026-07-31-assistant-run-timeout-design.md
Test-Path docs/superpowers/specs/2026-07-31-student-experience-refresh-design.md
rg -n "@/api/assistant" frontend/src
rg -n "agent_session" backend_python/app backend_python/tests
```

预期：四次 `Test-Path` 均为 `True`；所有引用均指向存在的恢复模块。

- [ ] **步骤 4：验证 Git 状态**

```powershell
git diff --check
git status --short
git log -4 --oneline
```

预期：无未提交恢复文件；最近提交包含规格、计划、后端恢复和前端恢复。

### 任务 4：完成全项目健康总览

**文件：**

- 创建：`docs/reviews/2026-08-01-project-health-overview.md`

- [ ] **步骤 1：收集架构与分层证据**

```powershell
rg --files backend_python/app frontend/src backend_python/alembic backend_python/alembic_assistant
rg -n "Depends\(|SessionLocal|AssistantSessionLocal|require_roles|get_current_user" backend_python/app
rg -n "localStorage|Authorization|refresh|401|403" frontend/src
```

检查路由是否保持薄层、CRUD 是否承载业务逻辑、助手工具是否独立创建数据库 Session、前端是否统一使用 Axios 包装器和 Vuex。

- [ ] **步骤 2：收集数据库、部署和依赖证据**

```powershell
Set-Location backend_python
D:\miniforge\envs\scientific_research\python.exe -m alembic -c alembic.ini heads
D:\miniforge\envs\scientific_research\python.exe -m alembic -c alembic_assistant.ini heads
D:\miniforge\envs\scientific_research\python.exe -m pip check
Set-Location ..
docker compose --env-file .env.docker config --quiet
Set-Location frontend
npm ls --depth=0
npm audit --omit=dev
```

记录双 Alembic 是否各只有一个 head、Compose 配置是否可解析、依赖是否损坏，以及生产依赖漏洞数量；`npm audit` 非零退出码作为风险证据，不自动执行 `npm audit fix --force`。

- [ ] **步骤 3：检查安全与仓库卫生**

```powershell
Set-Location ..
rg -n --hidden --glob '!.git/**' --glob '!node_modules/**' "(SECRET_KEY|API_KEY|PASSWORD|TOKEN)\s*=\s*['\"][^'\"]+['\"]" .
git ls-files | rg "(^|/)(\.env|uploads/|node_modules/|dist/|__pycache__/|\.pytest_cache/)"
git diff --check
```

只报告命中位置和风险类别，不在报告中复制密钥值。

- [ ] **步骤 4：编写分级报告**

创建 `docs/reviews/2026-08-01-project-health-overview.md`，固定包含以下章节：

```markdown
# 项目健康总览

## 执行摘要
## 已验证的健康项
## 必须修复
## 建议修改
## 仅供参考
## 验证命令与结果
```

每条问题包含证据文件、影响和建议方向；不得记录真实凭据内容，不把未验证推断写成事实。

- [ ] **步骤 5：验证并提交总览报告**

```powershell
$placeholderPattern = ('TO' + 'DO|TB' + 'D|待' + '定|后续' + '实现')
rg -n $placeholderPattern docs/reviews/2026-08-01-project-health-overview.md
git diff --check -- docs/reviews/2026-08-01-project-health-overview.md
git add -- docs/reviews/2026-08-01-project-health-overview.md
git commit -m "docs: 记录全项目健康总览（任务 4/4）"
```

预期：占位符扫描无命中，差异检查无错误，报告提交成功。
