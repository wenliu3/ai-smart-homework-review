# CI 回归恢复设计

## 背景

`main` 分支提交 `e723154` 以“移除旧版 assistant，统一到 chat 运行时”为目标，删除或缩减了多智能体助手运行时、前端助手 API 和 Vitest 配置。但现有全局助手、异步批改、查重解释、审批、运行产物和会话历史仍依赖这些模块，提交没有完成调用方、数据模型和测试的同步迁移。

当前可稳定复现以下故障：

- 后端导入 `app.main` 时因 `app.crud.agent_session` 缺失而失败。
- pytest 在收集阶段产生 59 个同源导入错误。
- 前端 Vitest 缺少 `jsdom` 环境和初始化文件，浏览器 API、样式导入与 DOMPurify 测试失败。
- 前端生产构建因 `src/api/assistant.ts` 被删除但仍被多个组件引用而失败。
- 本地 `node_modules` 存在已从 `package.json` 删除的残留依赖，可能掩盖干净安装问题。
- `chat` 路由将教师角色限制放宽为普通登录校验，形成权限边界回归。

## 目标

恢复 `e723154` 之前经过测试的助手运行时边界，使后端可以启动、前端可以生产构建、前后端完整测试可以执行，并保留该提交中新增加的设计与计划文档。

## 非目标

- 本次不重新设计助手架构。
- 本次不把 PostgreSQL 多智能体运行时迁移到 MySQL `AgentChatMessage`。
- 本次不删除审批、产物、取消、反馈、多角色助手或异步批改能力。
- 本次不顺带处理全项目总览中发现但与 `e723154` 无关的技术债。
- 本次不推送远端；是否提交和推送修复代码由用户后续决定。

## 方案

采用定向回滚：将 `e723154` 修改、删除的生产代码、测试和前端配置恢复为父提交 `56ff806` 中的版本，同时保留该提交新增的四份学生体验与助手超时文档。

### 后端恢复范围

- 恢复完整的 `app/crud/agent_session.py`。
- 恢复完整的 `app/crud/agent_run.py`，保留运行归属、步骤、产物、取消、失败和原子收口能力。
- 恢复 `app/routers/assistant.py`、`app/schemas/assistant.py` 及其在 `app/main.py` 中的注册。
- 恢复 `app/routers/chat.py` 的薄路由、教师角色限制、会话 ID 校验和助手数据库会话边界。
- 恢复 `app/agent/runtime.py` 与 `app/agent/tools/__init__.py` 的原有导出关系。
- 恢复被删除或大幅缩减的助手运行时测试，防止仅通过减少测试数量获得绿色 CI。

### 前端恢复范围

- 恢复 `src/api/assistant.ts`，满足全局助手、学生提交和教师评分面板的 API 契约。
- 恢复 `vitest.config.ts` 与 `src/__tests__/setup.ts`，使用 `jsdom` 并处理浏览器 API 和样式依赖。
- 恢复 `package.json` 中的测试脚本、DOMPurify、Vue Test Utils 和 jsdom 声明。
- 恢复被删除的助手 API 测试，确保 SSE 解析、会话、运行、审批和错误行为仍受回归保护。

### 保留范围

以下 `e723154` 新增文件继续保留：

- `docs/superpowers/plans/2026-07-31-assistant-run-timeout.md`
- `docs/superpowers/plans/2026-07-31-student-experience-refresh.md`
- `docs/superpowers/specs/2026-07-31-assistant-run-timeout-design.md`
- `docs/superpowers/specs/2026-07-31-student-experience-refresh-design.md`

## 数据与架构边界

恢复后继续保留两类助手数据边界：

- MySQL `AgentChatMessage`：教师快捷聊天历史。
- PostgreSQL `AgentSession`、`AgentRun`、`AgentMessage`、`AgentStep`、`AgentArtifact`：多角色助手、审批、产物、异步批改和审计运行时。

两者暂不合并。真正统一运行时需要单独规格，明确数据迁移、API 兼容、角色能力、审批与审计保留策略，不能通过直接删除其中一套完成。

## 实施与测试策略

现有失败命令就是本次回归测试的红灯证据。实施按以下顺序进行：

1. 机械恢复父提交中的目标文件，不修改四份保留文档。
2. 确认 `git diff` 只包含预期恢复和本规格/计划文档。
3. 运行后端导入检查、语法检查和完整 pytest。
4. 运行前端干净依赖一致性检查、完整 Vitest、类型检查和生产构建。
5. 对恢复后暴露的独立失败逐一执行红灯—最小修复—绿灯循环，不批量猜测式修改。
6. 运行 `git diff --check` 并复核工作区。

## 成功标准

- `python -c "import app.main"` 退出码为 0。
- `python -m compileall -q app` 退出码为 0。
- 后端完整 pytest 无失败和收集错误。
- 前端完整 Vitest 无失败。
- `npm run build` 同时通过 `vue-tsc` 与 Vite 生产构建。
- 不再存在指向已删除 `@/api/assistant` 或 `app.crud.agent_session` 的悬空引用。
- `git diff --check` 无错误。
- 四份指定新增文档保持存在。

## 后续全项目总览

恢复稳定基线后进行只读总览，覆盖：分层架构、双数据库与 Alembic、认证授权、文件上传、SSE/Agent 线程安全、Celery、Docker、前端路由与 Vuex、依赖一致性、测试覆盖和 CI。总览结果按“必须修复、建议修改、仅供参考”分级报告，不把审计发现自动混入本次恢复补丁。
