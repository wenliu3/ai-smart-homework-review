# 多智能体助手差距收敛总体规划（阶段 3A / 3B / 4 / 5）

> **面向 AI 代理的工作者：** 本文档是**分期总体规划**，不是可直接执行的实现计划。每期开工前，必须先用 superpowers:writing-plans 产出该期的细化实现计划（含 TDD 微步骤与完整代码），再用 superpowers:subagent-driven-development 或 superpowers:executing-plans 执行。
>
> 依据：2026-07-26 三智能体规格-实现差距盘点（49 条发现，去重后约 30 个独立缺口），基线提交 `941cc8c`。

**目标：** 把设计规格（`specs/2026-07-24-multi-agent-platform-design.md` 等）承诺但未实现/打折实现的功能，按价值分四期补齐，每期独立可交付、可验证。

**架构原则：** 复用现有骨架（LangGraph 角色图 + 审批执行机 + Celery 批改 + PG 会话库），只做增量接线与补齐，不推倒重来。已验证健壮的部分（审批执行机、批改幂等、角色隔离）不动。

**技术栈：** FastAPI + SQLAlchemy 2.0 + LangGraph + Celery/Redis + Vue 3 + Vuex；测试 pytest（双库 sqlite 替身，按 PID 并行）+ vitest。

**回归基线（任何一期不得低于）：** 后端 `python -m pytest -q` 359 通过；前端 `npx vitest run` 73 通过；`npx vue-tsc --noEmit` 零错误；`python -m compileall -q app` 通过。本机后端解释器 `D:/miniforge/envs/scientific_research/python.exe`。

---

## 分期总览

| 期 | 主题 | 为什么优先 | 预估规模 |
|----|------|-----------|---------|
| 3A | 教师写操作闭环 | 审批执行机已建好但教师完全用不到，投入产出比最高 | 中 |
| 3B | 批改质量回补 | 批改上下文相对旧版是功能回退，直接影响核心业务质量 | 中 |
| 4 | 可观测与反馈闭环 | Token/反馈/审计数据不落地，运营和评测无从谈起 | 中 |
| 5 | 智能化与体验升级 | 路由智能化、真流式、可视化——锦上添花，放最后 | 大 |

---

## 阶段 3A：教师写操作闭环

**交付定义：** 教师在助手聊天里说「帮我给张三的作业打 85 分」，能得到一张待审批草案卡片，在审批视图看到字段级差异并批准执行。

### 3A.1 教师图接入 ActionDraft

- 注册作业设计/写操作 specialist（`app/agent/registry.py` `_DEFAULT_SPECS` 新增），教师图新增 ActionDraft 意图与 `persist_action_draft` 节点（`app/agent/graphs/teacher.py`，复用 `subagents/__init__.py:persist_approval` 的管理员模式）。
- 主管词表新增写意图路由（`supervisors/teacher.py`：改分/发布/创建规则 → ACTION_DRAFT 而非 UNSUPPORTED_WRITE），保留最终审核对草案的确定性校验。
- 关键约束：草案 payload 服务端哈希、对象归属校验沿用 `crud/action_execution.py` 现有复验，不在图内做任何业务写。

### 3A.2 补齐审批白名单动作

- `contracts.py:ActionType` 新增 `publish_assignment` / `update_assignment` / `delete_assignment`（规格 §8.4 的 6 类补全；「删除资源」首期只落地删除作业，删除班级/学生风险高，列入范围外）。
- `crud/action_execution.py`：`_ROLE_ACTIONS` 登记 + 三个执行器（发布=状态迁移；修改=白名单字段 diff 应用；删除=软删或级联规则与现有 `crud/assignment.py` 对齐）。
- 每个动作配安全测试（越权/篡改/重复执行/归属错误），放 `tests/security/agent/`。

### 3A.3 approval.required SSE 事件

- `contracts.py` 事件契约新增 `approval.required`（携带 approvalId/summary/actionType）；教师与管理员编排在 `persist_action_draft` 成功后发出（`app/agent/service.py`）。
- 前端 `api/assistant.ts` 解析该事件，`AssistantPanel.vue` 在聊天流里插入审批提示卡片并联动切到审批视图。
- 兜底：写意图明确但未产出草案时（如管理员 `requires_approval=True` 而模型未返回 proposal，该字段现为死字段），finalize 返回「该操作需要审批但草案未生成，请重试或改用手动操作」提示，不再静默降级为普通分析（`graphs/admin.py` / `graphs/teacher.py` finalize 节点读取该标志）。

### 3A.4 前端教师审批入口与 diff 展示

- `role-config.ts` 教师 `canApprove: true`；`AssistantApprovalView.vue` 增加「历史」标签（`listApprovals` 已支持 status 参数，只差 UI）。
- 新增字段级 diff 组件（新建 `components/assistant/ApprovalDiff.vue`）：对 `update_*` 类动作展示旧值 → 新值（旧值由后端在草案 payload 里冗余快照，`crud/agent_approval.py` 创建时补采）；对 `create_*` 类动作展示结构化字段表而非裸 JSON。

**验收：** 教师聊天创建草案 → SSE 提示 → diff 审批 → 业务库落地全链路集成测试；三角色越权矩阵测试全绿。

---

## 阶段 3B：批改质量回补

**交付定义：** 批改 Agent 拿到与旧版同等的上下文（作业要求、参考附件、docx 内嵌图），失败时不再静默丢结果，教师能看到分维度评分。

### 3B.1 批改上下文补全

- `tasks/grading.py:_run_production_workflow` 把 `assignment.description` 与教师参考附件传入图状态；`subagents/grading.py` prompt 增加「作业要求」「参考资料」段（参考资料按不可信块包裹，防注入沿用 BEGIN/END_UNTRUSTED 模式）。
- `tools/content.py:normalize_submission_content` 对 .docx 增加内嵌图片提取（复用 `plagiarism/extractors.py:extract_all_from_docx` 现成能力），图片进 `image_refs`。
- 复核档位：`registry.py` grading_review 按提交是否含图动态选 `VISION_GRADER`/`REVIEWER`（`gateway.py` 已支持按 profile 取配置，只差选择逻辑）。

### 3B.2 失败降级与人工复核

- `contracts.py:GradingDraft` 增加 `confidence`、`requires_human_review`、`review_reasons`（规格 §8.2）；`graphs/grading.py:decide` 增加规则：证据为空、单项越界、结构化校验失败 → 转人工而非丢弃。
- `subagents/grading.py` 校验失败先做一次格式修复重试（把校验错误回喂模型一次），仍失败则保存原始草案文本到 artifacts 并标记 `needs_human_review`，`crud/submission.py:apply_ai_grading_result` 同步给教师端提示。
- `tasks/grading.py` 建 `RunBudget`（模型调用 ≤6 次、任务 ≤120s，规格 §15.2），`celery_app.py` 配 `soft_time_limit`。

### 3B.3 分维度结果暴露与进度接线

- `routers/assistant.py` 新增 `GET /assistant/runs/{run_id}/artifacts`（权限：run 归属人 + 该提交的任课教师；教师访问学生批改 run 需按 submission → assignment → teacher 链路校验）。
- 教师批改页展示分维度评分/证据（`views/teacher/correcting/` 新增草案面板）；学生提交后用已返回的 `gradingRunId` 轮询 `GET /assistant/runs/{run_id}` 显示批改进度。

### 3B.4 查重解释修复

- `crud/plagiarism_suggestion.py`：作业内容（截断 + 不可信块）重新传入解释节点，删除死参数或恢复其用途，二选一后同步 docstring；`_build_suggestion_prompt` 死代码删除。
- 解释运行落 `AgentRun`/`Artifact`（复用批改的系统会话模式），`graphs/plagiarism.py` 增加最终审核节点（对照架构手册 §6 的 Explain→Review→Output）。Celery 化列入范围外（同步耗时可接受时不做）。

**验收：** 带 docx 内嵌图的提交批改集成测试；格式漂移用例转人工而非失败；教师端能看到分维度结果。

---

## 阶段 4：可观测与反馈闭环

### 4.1 Token 用量采集
`gateway.py` 从 LangChain 响应 `usage_metadata` 采集 token，经回调写 `AgentStep.usage_json` / `AgentRun.usage_json`（列已存在，零写入方）；`AiModel.total_usage/total_tokens` 的自增迁移到网关层（旧自增点在死代码里）。管理员 `query_model_governance_metrics` 数据恢复真实。

### 4.2 模型容错
`AGENT_MODEL_TIMEOUT` 错误码接线（超时异常单独捕获）；瞬时错误重试一次；模型调用超时按 `RunBudget.remaining_seconds` 收紧（规格阶段 1.5 §6）。备用模型切换依赖模型能力标签与按档位绑定机制（列入 5.3），本期只做同模型重试。

### 4.3 反馈闭环
新表 `agent_feedback`（`alembic_assistant` 新 revision）+ `POST /assistant/runs/{run_id}/feedback` + 前端消息气泡 👍/👎 与教师改分幅度自动采集（`apply_ai_grading_result` 后教师改分时记录差值）。

### 4.4 运行明细与会话管理
`GET /assistant/runs/{run_id}` 响应扩展 steps 摘要；会话删除/改名接线（`crud/agent_session.py:delete_session` 已写好零调用；补 `DELETE /assistant/sessions/{id}` 与前端历史视图按钮）；Step 生命周期补 `running`/`cancelled` 状态；会话摘要在 finalize 后生成写回 `AgentSession.summary`（列已存在零写入方）；审批过期治理——`list_owned_approvals` 过滤或标记已过期草案，前端待审批列表不再永久展示过期项（现仅惰性过期）。

### 4.5 Checkpoint 策略（先决设计决策 D3）
按决策结果二选一：聊天路径 `checkpointer=None`（无恢复消费方，省存储）；或保留并加定期清理任务（`PostgresSaver.delete_thread`，按 run 完成时间）。

### 4.6 死代码清理
删除 `crud/submission.py:268-514` 旧直连批改链路（约 250 行，注意先完成 4.1 的用量口径迁移）；删除 `graphs/approval.py` 死图或补真实接线（按决策 D4）。

**验收：** 一次真实聊天/批改后 usage_json 非空、模型用量增长；反馈可落库可查询；会话可删可改名。

---

## 阶段 5：智能化与体验升级

- **5.1 LLM 路由兜底：** 三角色主管在关键词未命中时调一次 `ROUTER` 档位模型分类（规格允许最多一次），路由评测集补对抗样本，95% 门槛可度量。
- **5.2 防代写加固：** 学生请求与进行中作业题面相似度比对（工具侧新增题面只读查询）、输出长度/完整度约束；概念讲解类意图豁免「本人数据证据」硬门槛（`student_final_reviewer.py` 按意图分流）。
- **5.3 管理员数据源与模型治理增强：** 新增 OperationLog 聚合工具（登录失败/权限拒绝/操作频率）、活跃度与班级规模统计、模型连通性探测工具；`AiModel` 增加能力标签（多模态/文本）与按档位绑定，支撑备用模型切换（衔接 4.2）；受控正文访问端点（单独授权 + 写操作日志，规格 §14.2）。
- **5.4 真流式与运行可视化：** 学生/管理员编排改 `graph.astream`（对齐教师路径的节点级事件）；审核后统一切片的伪流式改为「审核通过段落逐段放行」（需决策 D5）；前端运行步骤时间线 + 工具调用 + Artifact 卡片（消费 3B.3/4.4 的接口）。
- **5.5 多意图拆解：** 激活 `AgentTask` 契约，教师主管支持 ≤5 子任务拆解与无依赖只读并行（规格 §7.2）。规模大，建议单独立项。
- **5.6 平台开关：** `MULTI_AGENT_ENABLED` 功能开关 + 教师白名单灰度；`page_context` 请求字段与图状态接线。
- **5.7 评测真实化：** 录制回放式评测替换 70 条自证 fixture，含多模态批改用例与人工评分标准字段。

---

## 先决设计决策（各期细化计划前需逐项拍板）

| # | 决策点 | 影响 | 倾向建议 |
|---|--------|------|---------|
| D1 | 「删除资源」审批动作的范围（仅作业？含班级/学生？） | 3A.2 | 首期仅作业软删 |
| D2 | 教师草案 diff 的旧值快照存草案 payload 还是审批时实查 | 3A.4 | 存 payload（审批时点一致性） |
| D3 | checkpoint 关闭 vs 保留+清理 | 4.5 | 聊天关，批改保留+清理 |
| D4 | `graphs/approval.py` 删除 vs 接线 | 4.6 | 删除（CRUD 层已是事实标准） |
| D5 | 真流式是否允许「审核前先流出、审核否决后撤回」 | 5.4 | 不允许，改为审核通过逐段放行 |
| D6 | 防代写误杀与漏放的平衡（概念题豁免的边界） | 5.2 | 按意图豁免 + 题面相似度兜底 |

## 范围外（本轮明确不做）

- 语音/多语言、跨教师协作会话等规格从未承诺的能力。
- 查重 Celery 化（同步耗时可接受）。
- 删除班级/学生等高风险审批动作（见 D1）。
- 旧 `/teacher/assistant/*` 接口下线（等 `MULTI_AGENT_ENABLED` 灰度完成后单独处理）。

## 执行流程（每期相同）

1. 拍板该期涉及的先决决策 → 2. superpowers:writing-plans 产出该期细化实现计划（TDD 微步骤 + 完整代码）→ 3. subagent-driven-development 执行 → 4. 回归基线 + 该期验收标准全绿 → 5. 分组提交 → 6. 本文档勾掉该期并更新 README 状态表。

- [x] 阶段 3A：教师写操作闭环（2026-07-26 完成；决策采用 D1 仅作业软删、D2 快照存 payload）
- [x] 阶段 3B：批改质量回补（2026-07-26 完成；查重 Celery 化按范围外未做）
- [x] 阶段 4：可观测与反馈闭环（2026-07-27 完成；D3 按「聊天关、批改本就未接线」落地，D4 死图与旧直连链路已删）
- [ ] 阶段 5：智能化与体验升级
