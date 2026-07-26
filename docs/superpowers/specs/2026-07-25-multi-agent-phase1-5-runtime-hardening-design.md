# 教师只读多智能体阶段 1.5 运行时收口设计

> 日期：2026-07-25
> 状态：待实现
> 范围：教师只读多智能体；不包含批改、查重、写操作审批、学生与管理员 Agent

## 1. 目标

将阶段 1 已完成的教师多智能体骨架收口为可安全运行、可真实流式、可取消、可追踪的 LangChain/LangGraph v1 实现，并升级到 2026-07-25 的最新稳定依赖。

本阶段完成后：

- 所有 Agent 使用 `langchain.agents.create_agent`，不使用已弃用的 `langgraph.prebuilt.create_react_agent`。
- 专业 Agent 和最终审核使用 Pydantic 结构化输出，不再手工解析模型 JSON 文本。
- LangGraph 使用 `StateGraph` 和 `stream(..., version="v2")` 输出真实节点事件。
- `run.started` 在任何耗时操作前发送并携带 `run_id`。
- 用户取消、运行预算和总超时在节点边界生效，已取消运行不得被覆盖成完成。
- 会话摘要和最近消息窗口进入专业 Agent 上下文。
- Step、Artifact、Evidence 和最终消息反映真实执行结果。

## 2. 依赖基线

锁定以下稳定版本：

```text
langchain==1.3.14
langchain-openai==1.4.1
langchain-core==1.5.1
langgraph==1.2.9
```

使用 `D:\miniforge\envs\scientific_research\python.exe` 安装和验证。升级后先运行导入、API 签名和现有测试兼容性检查，再修改业务实现。

## 3. 运行架构

```text
FastAPI SSE
  → 创建 Session/Run，立即发送 run.started(run_id)
  → LangGraph v2 stream
      → route
      → teaching_data | teaching_strategy
      → deterministic evidence guard
      → final_reviewer
      → finalize
  → 节点事件实时转换为安全 SSE
  → PostgreSQL 原子完成 Run、Artifact、最终消息
```

保留“角色主管 + 专业 Agent + 确定性工具 + 最终审核”的现有架构，不引入自由 Agent 交接网络，也不在本阶段引入 LangGraph Checkpointer。

## 4. 结构化输出与证据链

### 4.1 专业 Agent 输出

专业 Agent 返回新的 `SpecialistResponse`：

```python
class SpecialistResponse(BaseModel):
    answer: str
    evidence_refs: list[str]
    limitations: list[str] = []
```

工具继续从服务端上下文获得教师身份，但将 `TeachingQueryResult` 序列化为结构化 JSON ToolMessage，而不是拼接不可校验的自然语言。旧 `/teacher/assistant/*` 兼容接口可在边界格式化文本，但新版多智能体内部不得使用旧字符串工具结果。

### 4.2 最终审核

最终审核 Agent 通过 `create_agent(response_format=ReviewResult)` 获取 `structured_response`。任何以下情况均拒绝并安全降级：

- 缺少 `structured_response`。
- Pydantic 校验失败。
- 模型超时或调用异常。
- 事实性回答没有证据。
- 候选回答包含敏感字段或内部实现信息。

审核器不得再使用 `json.loads()`、代码围栏截取或 `bool(value)` 转换。

### 4.3 确定性预检

在调用最终审核 Agent 前执行确定性证据预检：

- 含事实指标的回答必须有 `evidence_refs`。
- Evidence URI 只能使用允许的 scheme 和当前运行生成的引用。
- 候选回答为空、证据为空或结构校验失败时不调用审核模型，直接拒绝。

## 5. 真实流式与取消

### 5.1 SSE

服务先创建 Run，再立即发送：

```json
{"type":"run.started","data":{"run_id":"..."}}
```

随后消费 LangGraph `stream(..., version="v2")`，按节点实际开始和结束时间发送：

- `route.selected`
- `agent.started`
- `agent.completed`
- `content.delta`
- `run.completed`
- `run.failed`
- `run.cancelled`
- `heartbeat`

最终答案可在审核通过后按安全文本分块发送 `content.delta`。未经审核的 specialist 输出不得流向前端。

### 5.2 取消

取消 API 使用条件更新，仅允许 `running → cancelled`。每个图节点开始前查询 Run 状态；发现 cancelled 时抛出稳定的 `RunCancelled`，停止后续 Agent 调用。

`finalize_run` 使用条件更新，只允许仍为 running 的 Run 完成。若 Run 已取消，不写最终消息、不写 completed 状态。

客户端中断网络连接后，若已经取得 `run_id`，继续调用取消 API。服务端不得依赖客户端连接关闭来判断取消。

## 6. 预算和超时

生产入口必须创建默认 `RunBudget(max_nodes=8, max_tool_calls=12, timeout_seconds=45)`，不得传 `None`。

- 节点开始前消费节点预算。
- 每次工具调用通过 LangChain v1 `wrap_tool_call` middleware 消费工具预算。
- 模型调用超时不得超过剩余总预算。
- 总预算超限返回 `AGENT_BUDGET_EXCEEDED`。
- 用户取消返回 `AGENT_RUN_CANCELLED`。
- 模型自身超时返回 `AGENT_MODEL_TIMEOUT`。

本阶段不使用无法中断线程的伪超时作为安全保证；模型 HTTP 超时负责中止单次调用，节点边界负责总预算和取消。

## 7. 会话上下文

每次运行从 PostgreSQL 读取：

- 当前会话 `summary`。
- 最近十条已完成的 user/assistant 消息。

上下文以 LangChain Message 对象传给专业 Agent，并在末尾追加本轮用户消息。不同用户、角色和会话之间不得复用摘要。

本阶段只读取已有 summary，不新增自动摘要模型调用；自动摘要仍属于后续质量优化阶段。

## 8. 持久化与可观测性

每个节点执行时实时写 Step：

- `running`：节点开始、开始时间。
- `completed`：结构化输出摘要、证据引用、用量、耗时。
- `failed/cancelled`：稳定错误码和耗时。

`AnalysisArtifact` 和 `ReviewResult` 作为带 `schema_version` 的 Artifact 保存。Run 的 `intent` 和 `risk_level` 在路由完成后更新为真实值，不再固定为 `teacher_query/low`。

Step sequence 增加数据库唯一约束 `(run_id, sequence)`；本阶段单 Run 顺序执行，不实现并行节点序号分配。

## 9. 兼容策略

- 新 `/assistant/*` 使用新版结构化运行时。
- 旧 `/teacher/assistant/*` 暂时保留纯文本 SSE，但底层 Agent 构建统一使用新版 `create_agent`。
- `tools/legacy.py` 只服务旧接口，新图不得导入 `ALL_TOOLS`。
- 不删除旧接口和旧聊天表，待前端迁移稳定后另立清理计划。

## 10. 测试与验收

必须先增加失败测试，再修改生产代码。覆盖：

1. 审核非 JSON、字符串 `"false"`、空结构化输出全部拒绝。
2. `run.started` 首事件包含真实 `run_id`。
3. 图执行期间能观察到阶段事件，而不是完成后批量返回。
4. 取消后不再调用下一个 Agent，且最终状态保持 cancelled。
5. 生产入口一定创建默认预算；第十三次工具调用失败。
6. 45 秒总预算和模型超时返回不同稳定错误码。
7. 第二轮请求能读取同会话最近消息，跨会话不可见。
8. 专业 Agent 产物、证据、审核结果和 Step 真实落库。
9. 旧接口兼容测试继续通过。
10. 依赖版本精确匹配本规格。

最终验证：

```powershell
& "D:\miniforge\envs\scientific_research\python.exe" -m pytest tests -q -p no:cacheprovider --basetemp "<workspace-temp>"
& "D:\miniforge\envs\scientific_research\python.exe" -m compileall -q app
npm.cmd test
npx.cmd vue-tsc --noEmit
docker compose config
```

若前端存在历史类型错误，必须单独列出；本阶段修改文件不得新增错误。

## 11. 非目标

- 不实现批改或查重工作流。
- 不实现 Agent 写操作审批。
- 不实现学生或管理员主管。
- 不引入 Celery、Redis、LangSmith 或向量数据库。
- 不自动升级未来发布的新版本；本规格只锁定 2026-07-25 已发布的稳定版本。
