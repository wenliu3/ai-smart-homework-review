# Superpowers 开发文档索引

本目录只保存多智能体平台的规格、实施计划和执行历史。业务说明继续放在项目根目录 `README.md`。

## 阅读顺序

1. [多智能体平台架构与 Graph 维护手册](AGENT_ARCHITECTURE.md)
2. [多智能体平台设计规格](specs/2026-07-24-multi-agent-platform-design.md)
3. [阶段 1.5 运行时收口设计](specs/2026-07-25-multi-agent-phase1-5-runtime-hardening-design.md)
4. [差距收敛总体规划（阶段 3A/3B/4/5，当前执行依据）](plans/2026-07-26-multi-agent-gap-closure-roadmap.md)

## 目录约定

```text
docs/superpowers/
├── README.md              # 唯一阅读入口和进度说明
└── specs/                 # 已确认的目标架构与行为规格
```

历史实施计划（plans/）已在全部阶段完成后清理（2026-07-26），执行历史以 git 提交记录为准。

## 当前状态

| 范围 | 状态 | 说明 |
|---|---|---|
| 阶段 0：基础治理与 PostgreSQL Agent 状态库 | 已完成 | 后端回归测试通过，双 Alembic 迁移可升降级 |
| 阶段 1：教师只读多智能体 | 已完成 | 教师主管、专业 Agent、审核与结构化工具已接线；关键词未命中时走一次 ROUTER 档位 LLM 兜底分类（写意图不可由 LLM 授予，规划 5.1） |
| 阶段 2：批改与查重工作流 | 已完成 | 双 Agent 批改 + 3B 回补：作业要求/参考附件/docx 内嵌图进批改上下文、含图提交复核走 VISION_GRADER、结构化失败一次修复重试后转人工（原始草案留证）、RunBudget（模型调用≤6/120s）+ Celery 软超时、分维度产物接口与教师面板、学生 gradingRunId 进度轮询、查重解释带作业内容且经审核落 Run |
| 阶段 3：写操作审批 | 已完成 | 审批执行机 + 教师写操作闭环：ACTION_DRAFT 路由、`teacher_action` specialist、`persist_action_draft` 节点、`approval.required` 事件、作业发布/修改/软删三动作、教师审批入口与字段级 diff |
| 阶段 4：学生助手 | 已完成 | 辅导、反馈解释、学习规划可用；防代写加固（规划 5.2）：进行中作业题面 4-gram 相似度兜底（阈值 0.55，题面查询仅服务端调用不暴露给 LLM）、辅导回答 1200 字完整度上限、概念讲解意图豁免本人数据证据硬门槛 |
| 阶段 5：管理员助手 | 已完成 | 聚合运营、代码级脱敏、模型治理草案可用；5.3 增强：OperationLog 审计聚合（登录失败/权限拒绝/高频端点）、活跃度与班级规模统计、模型连通性探测、AiModel 能力标签与档位绑定（VISION_GRADER 动态选型）、受控正文访问端点（superadmin 单独授权 + 操作日志留痕，绝不记录正文本身） |
| 阶段 6：质量与成本优化 | 已完成 | 预算/取消/运行落库 + 阶段 4 回补：Step/Run 级 Token 用量与 AiModel 原子自增、模型超时稳定码与瞬时重试、agent_feedback 反馈闭环（👍/👎 + 教师改分差值）、会话删除/改名/摘要、Step 生命周期 running/cancelled、审批惰性过期、聊天 checkpointer 摘除与死代码清理；评测真实化（5.7）：70 条录制回放用例驱动真实解析/校验/修复重试/降级/查重管线，含多模态批改与人工评分校准（偏差 ≤ 满分 10%） |
| 阶段 7：智能化与体验升级（规划 5） | 已完成（5.5 单独立项） | 学生/管理员编排改 astream 真流式（节点级事件 + 审核通过后逐段放行，D5）、前端运行时间线与产物卡片、`MULTI_AGENT_ENABLED` 总开关 + 教师白名单灰度、`page_context` 请求字段进图状态；5.5 多意图拆解规模大按规划建议单独立项未随本期实施 |
| 生产加固 | 已完成 | 容器双迁移（含既有库 stamp）、批改重投递、审批竞态、SSE 完整性和并发上限 |

尚未实现/打折实现的功能全集与分期安排见[差距收敛总体规划](plans/2026-07-26-multi-agent-gap-closure-roadmap.md)（2026-07-26 盘点）。

2026-07-27 阶段 3A/3B/4/5 后仓库级验证：

- Conda 解释器：`D:\miniforge\envs\scientific_research\python.exe`（Python 3.12.13）。
- 后端全量：640 passed（阶段 3A 前基线 359，阶段 4 后 582）；前端全量：136 passed（基线 73，阶段 4 后 126）。
- 阶段 3A 后做了一轮多视角对抗式审查（25 条发现，驳回 21 条），确认并修复 4 条：
  批改队列未过滤软删作业、删用户守卫漏算软删作业致外键孤儿、
  只读提问被写意图词误判、修订路径残留上一轮草案被误落审批。
- `vue-tsc --noEmit`、Vite 生产构建、Python `compileall` 均通过。
- 双 Alembic 单 head：业务库 `e2b6c9d4a7f1`（ai_models.capabilities/profile_bindings，
  上一版 `c4e9a1b6d2f8` 为 assignments.deleted_at 软删列 + submissions.grading_run_id），
  会话库 `20260727_03`（agent_feedback 表）。
- 离线评测 110 条：40 条路由（含 9 条关键词全 miss 的 LLM 兜底对抗样本）+
  70 条录制回放（`tests/evals/recordings/`，schema_version 1.x 兼容加载）。
- 软删不变式：所有读取 Assignment 的查询（含 join / count）必须带 `Assignment.alive()`，
  软删作业与硬删对调用方等价不可见；提交记录保留以便误删恢复。
- Docker 必须使用 `docker compose --env-file .env.docker up -d`；仅 backend 执行双库迁移，worker 只启动 Celery，避免并发迁移。
- 自动化验证不替代真实三角色账号和外部模型/Redis 的端到端联调。

## 维护规则

- 规格发生架构变化时更新 `specs/`。
- 新的实施计划在执行期间可临时放入 `plans/`，完成验证后清理，不长期保留。
- 不在本目录保存测试输出、临时分析、截图或生成文件。
