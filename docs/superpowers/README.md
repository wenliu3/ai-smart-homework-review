# Superpowers 开发文档索引

本目录只保存多智能体平台的规格、实施计划和执行历史。业务说明继续放在项目根目录 `README.md`，代码约定继续放在 `AGENTS.md`。

## 阅读顺序

1. [多智能体平台架构与 Graph 维护手册](AGENT_ARCHITECTURE.md)
2. [多智能体平台设计规格](specs/2026-07-24-multi-agent-platform-design.md)
3. [阶段 1.5 运行时收口设计](specs/2026-07-25-multi-agent-phase1-5-runtime-hardening-design.md)

## 目录约定

```text
docs/superpowers/
├── README.md              # 唯一阅读入口和进度说明
└── specs/                 # 已确认的目标架构与行为规格
```

历史实施计划（plans/）已在全部阶段完成后清理（2026-07-26），执行历史以 git 提交记录为准。

## 当前状态

| 范围 | 状态 | 验证 |
|---|---|---|
| 阶段 0：基础治理与 PostgreSQL Agent 状态库 | 已完成 | 后端回归测试通过，双 Alembic 迁移可升降级 |
| 阶段 1：教师只读多智能体 | 已完成 | 教师主管、专业 Agent、审核与结构化工具已接线 |
| 阶段 2：批改与查重工作流 | 已完成 | 双 Agent 批改、确定性查重、Celery/Redis 长任务与版本幂等 |
| 阶段 3：写操作审批 | 已完成 | ActionDraft、行锁、白名单执行、对象归属与跨库幂等 |
| 阶段 4：学生助手 | 已完成 | 辅导、反馈解释、学习规划和防代写 |
| 阶段 5：管理员助手 | 已完成 | 聚合运营、脱敏审计和模型治理建议 |
| 阶段 6：质量与成本优化 | 已完成 | 100 条离线评测、预算、取消、Checkpointer 和运行审计 |
| 生产加固 | 已完成 | 容器双迁移、批改重投递、审批竞态、多模态图片、SSE 完整性和并发上限 |

2026-07-25 最终仓库级验证：

- Conda 解释器：`D:\miniforge\envs\scientific_research\python.exe`（Python 3.12.13），`pip check` 无冲突。
- 后端全量：298 passed；前端全量：61 passed。
- `vue-tsc --noEmit`、Vite 生产构建、Python `compileall`、双 Alembic head、入口脚本语法和 Compose 配置均通过。
- Docker 必须使用 `docker compose --env-file .env.docker up -d`；仅 backend 执行双库迁移，worker 只启动 Celery，避免并发迁移。
- 自动化验证不替代真实三角色账号和外部模型/Redis 的端到端联调。

## 维护规则

- 规格发生架构变化时更新 `specs/`。
- 新的实施计划在执行期间可临时放入 `plans/`，完成验证后清理，不长期保留。
- 不在本目录保存测试输出、临时分析、截图或生成文件。
