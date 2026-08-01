# 可选独立结构化模型批改链路实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让超级管理员决定是否使用独立结构化模型；关闭时由教师 AI 规则指定模型直接结构化，开启时由该模型生成两份普通批改报告，再由管理员指定模型统一转换为可校验结果，同时彻底消除无限模型调用和僵尸 Run。

**架构：** 复用 `ai_models.profile_bindings` 表示全局 `grading_structurer` 绑定，不新增密钥存储。批改图扩展为“直接结构化”和“普通报告 + 独立结构化”两条显式路径，所有模型按明确 code 路由并限制递归。Celery 父进程硬超时收口与 Run 读取时陈旧状态修复构成双重防线，学生端渲染真实终态。

**技术栈：** FastAPI、SQLAlchemy、Pydantic、LangChain 1.3、LangGraph、Celery 5.6、Redis、Vue 3、TypeScript、Element Plus、pytest、Vitest。

---

## 文件职责

### 后端配置与模型网关

- 修改 `backend_python/app/agent/contracts.py`：新增 `GRADING_STRUCTURER` 档位和双报告结构化契约。
- 修改 `backend_python/app/schemas/ai_model.py`：新增结构化模型绑定请求与能力测试响应 Schema。
- 修改 `backend_python/app/crud/ai_model.py`：实现绑定读取、唯一切换、关闭和能力测试业务逻辑。
- 修改 `backend_python/app/routers/ai_models.py`：增加超级管理员结构化模型配置端点。
- 修改 `backend_python/app/agent/gateway.py`：支持按模型 code 精确取模型，并禁止结构化档位隐式回退默认模型。
- 修改 `backend_python/app/agent/registry.py`：按模型 code 和输出模式构建批改 Agent。
- 创建 `backend_python/tests/unit/agent/test_grading_structurer_config.py`：覆盖绑定和网关选择。
- 修改 `backend_python/tests/security/agent/test_ai_model_access.py`：覆盖新端点权限与密钥脱敏。

### 批改编排与超时

- 修改 `backend_python/app/agent/graphs/grading.py`：增加可选结构化节点和普通报告状态字段。
- 修改 `backend_python/app/agent/subagents/grading.py`：支持普通文本与直接结构化两种调用模式，限制递归。
- 修改 `backend_python/app/agent/subagents/grading_review.py`：复核使用同一 AI 规则模型并支持两种模式。
- 创建 `backend_python/app/agent/subagents/grading_structurer.py`：把两份普通报告一次转换为双草案。
- 修改 `backend_python/app/tasks/grading.py`：根据管理员绑定选择路径、按规则模型 code 路由、分别记录用量和产物。
- 创建 `backend_python/app/tasks/grading_request.py`：Celery 5.6 父进程硬超时收口。
- 修改 `backend_python/app/crud/agent_run.py`：陈旧批改 Run 的确定性收口。
- 修改 `backend_python/app/routers/assistant.py`：在返回 Run 前调用 CRUD 收口函数。
- 修改批改单元/集成测试：覆盖双路径、有限调用、版本隔离、硬超时和陈旧 Run。

### 规则快照与管理员/学生前端

- 修改 `frontend/src/views/teacher/assignments/components/AiRuleSelector.vue`：规则快照保留 `maxScore`。
- 修改 `frontend/src/api/ai-rule.ts`：补齐 `maxScore` 类型。
- 修改 `frontend/src/api/ai-models.ts`：增加结构化模型配置与能力测试 API。
- 修改 `frontend/src/views/system/ai_model/index.vue`：增加全局开关、模型选择和结构化能力测试。
- 创建 `frontend/src/views/system/ai_model/__tests__/GradingStructurerSettings.spec.ts`：覆盖管理员交互。
- 修改 `frontend/src/views/student/submissions/composables/useSubmissionManagement.ts`：暴露真实 Run 状态和错误码。
- 修改 `frontend/src/views/student/submissions/components/ReviewResults.vue`：持久展示失败/取消状态。
- 修改现有学生端测试：覆盖 processing、failed、cancelled 和轮询上限。

## 任务 1：定义结构化模型配置与契约

**文件：**
- 修改：`backend_python/app/agent/contracts.py`
- 修改：`backend_python/app/schemas/ai_model.py`
- 创建：`backend_python/tests/unit/agent/test_grading_structurer_config.py`

- [ ] **步骤 1：编写失败的契约测试**

新增测试，要求模型档位和双报告返回结构存在：

```python
from app.agent.contracts import (
    GradingReportPair,
    GradingDraft,
    ModelProfile,
)


def test_grading_structurer_profile_and_pair_contract():
    assert ModelProfile.GRADING_STRUCTURER.value == "grading_structurer"
    payload = {
        "schema_version": "v1",
        "primary": {
            "rubric_version": "rubric-v1",
            "items": [{
                "criterion_id": "overall",
                "title": "综合质量",
                "score": 86,
                "max_score": 100,
                "feedback": "完成主要任务",
                "evidence_refs": ["submission:attachment:1"],
            }],
            "summary": "主批改报告",
        },
        "review": {
            "rubric_version": "rubric-v1",
            "items": [{
                "criterion_id": "overall",
                "title": "综合质量",
                "score": 82,
                "max_score": 100,
                "feedback": "部分分析不足",
                "evidence_refs": ["submission:attachment:1"],
            }],
            "summary": "独立复核报告",
        },
    }
    pair = GradingReportPair.model_validate(payload)
    assert isinstance(pair.primary, GradingDraft)
    assert pair.review.total_score == 82
```

再验证绑定请求：

```python
from app.schemas.ai_model import GradingStructurerBindingUpdate


def test_structurer_binding_requires_model_when_enabled():
    with pytest.raises(ValidationError):
        GradingStructurerBindingUpdate(enabled=True)
    assert GradingStructurerBindingUpdate(enabled=False).modelCode is None
```

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_structurer_config.py -q
```

预期：FAIL，提示 `GRADING_STRUCTURER`、`GradingReportPair` 或请求 Schema 不存在。

- [ ] **步骤 3：实现最小契约**

在 `ModelProfile` 增加：

```python
GRADING_STRUCTURER = "grading_structurer"
```

增加：

```python
class GradingReportPair(BaseModel):
    schema_version: str = "v1"
    primary: GradingDraft
    review: GradingDraft
    extraction_errors: list[str] = Field(default_factory=list)
```

请求 Schema 使用模型级校验：

```python
class GradingStructurerBindingUpdate(BaseModel):
    enabled: bool
    modelCode: str | None = None

    @model_validator(mode="after")
    def require_model_when_enabled(self):
        if self.enabled and not (self.modelCode or "").strip():
            raise ValueError("启用独立结构化模型时必须选择模型")
        if not self.enabled:
            self.modelCode = None
        return self
```

- [ ] **步骤 4：运行测试并确认绿灯**

运行同一 pytest 命令，预期全部 PASS。

- [ ] **步骤 5：提交任务 1**

```powershell
git add backend_python/app/agent/contracts.py backend_python/app/schemas/ai_model.py backend_python/tests/unit/agent/test_grading_structurer_config.py
git commit -m "test: define optional grading structurer contracts"
```

## 任务 2：实现管理员结构化模型绑定 API

**文件：**
- 修改：`backend_python/app/crud/ai_model.py`
- 修改：`backend_python/app/routers/ai_models.py`
- 修改：`backend_python/tests/unit/agent/test_grading_structurer_config.py`
- 修改：`backend_python/tests/security/agent/test_ai_model_access.py`

- [ ] **步骤 1：编写失败的 CRUD 测试**

测试构造 `deepseek`、`mimo` 两条模型记录并断言：

```python
assert ai_model_crud.get_grading_structurer_binding(db) == {
    "enabled": False,
    "modelCode": None,
    "model": None,
}

result = ai_model_crud.set_grading_structurer_binding(
    db, enabled=True, model_code="deepseek",
)
assert result["enabled"] is True
assert result["modelCode"] == "deepseek"

deepseek = db.query(AiModel).filter(AiModel.code == "deepseek").one()
mimo = db.query(AiModel).filter(AiModel.code == "mimo").one()
assert deepseek.profile_bindings == {"grading_structurer": True}
assert not (mimo.profile_bindings or {}).get("grading_structurer")

ai_model_crud.set_grading_structurer_binding(
    db, enabled=True, model_code="mimo",
)
db.refresh(deepseek)
db.refresh(mimo)
assert not (deepseek.profile_bindings or {}).get("grading_structurer")
assert mimo.profile_bindings["grading_structurer"] is True

ai_model_crud.set_grading_structurer_binding(db, enabled=False)
db.refresh(mimo)
assert not (mimo.profile_bindings or {}).get("grading_structurer")
```

分别断言 inactive、空 API Key 和不存在模型抛出稳定业务异常。

- [ ] **步骤 2：运行 CRUD 测试并确认红灯**

运行任务 1 的测试文件，预期 FAIL，提示绑定函数不存在。

- [ ] **步骤 3：实现唯一绑定事务**

实现私有序列化函数，不返回明文密钥；切换时逐行复制 JSON，避免原地修改未被 SQLAlchemy 追踪：

```python
def _set_structurer_flag(model: AiModel, enabled: bool) -> None:
    bindings = dict(model.profile_bindings or {})
    if enabled:
        bindings["grading_structurer"] = True
    else:
        bindings.pop("grading_structurer", None)
    model.profile_bindings = bindings or None
```

`set_grading_structurer_binding()` 在一个事务内锁定模型行、验证目标、清除旧绑定、设置新绑定并提交。`get_grading_structurer_binding()` 若发现多条历史脏绑定，抛配置冲突而不是随意选择第一条。

- [ ] **步骤 4：增加超级管理员端点**

增加：

```python
@router.get("/admin/ai-models/grading-structurer/config")
def get_grading_structurer_config(
    current_user: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    return ok(ai_model_crud.get_grading_structurer_binding(db))


@router.put("/admin/ai-models/grading-structurer/config")
def update_grading_structurer_config(
    body: GradingStructurerBindingUpdate,
    current_user: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    return ok(ai_model_crud.set_grading_structurer_binding(
        db,
        enabled=body.enabled,
        model_code=body.modelCode,
    ))
```

静态路径必须放在 `/{code}` 动态路径之前，防止被解析成模型 code。

- [ ] **步骤 5：补权限与脱敏测试**

在安全测试中断言 student/teacher 访问 GET/PUT 均为 403；superadmin 可访问；响应的 `model` 只包含掩码 `apiKey`，不包含数据库明文。

- [ ] **步骤 6：运行测试并确认绿灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_structurer_config.py backend_python/tests/security/agent/test_ai_model_access.py -q
```

预期全部 PASS。

- [ ] **步骤 7：提交任务 2**

```powershell
git add backend_python/app/crud/ai_model.py backend_python/app/routers/ai_models.py backend_python/tests/unit/agent/test_grading_structurer_config.py backend_python/tests/security/agent/test_ai_model_access.py
git commit -m "feat: configure optional grading structurer model"
```

## 任务 3：让网关严格按 AI 规则模型 code 路由

**文件：**
- 修改：`backend_python/app/agent/gateway.py`
- 修改：`backend_python/app/agent/registry.py`
- 创建：`backend_python/tests/unit/agent/test_grading_model_routing.py`

- [ ] **步骤 1：编写失败的精确路由测试**

使用两个模型配置和假的 `init_chat_model`，断言：

```python
gateway.get_chat_model_by_code(
    db,
    model_code="mimo",
    profile=ModelProfile.VISION_GRADER,
    prompt_version="v1",
)
assert captured[-1]["model"] == "openai:mimo-v2.5"

gateway.get_chat_model_by_code(
    db,
    model_code="deepseek",
    profile=ModelProfile.VISION_GRADER,
    prompt_version="v1",
)
assert captured[-1]["model"] == "openai:deepseek-chat"
```

把默认模型切换为另一条后再次断言结果不变。不存在、inactive、无 Key 均应抛 `MODEL_NOT_CONFIGURED_CODE`，禁止默认回退。

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_model_routing.py -q
```

预期 FAIL，提示 `get_chat_model_by_code` 不存在。

- [ ] **步骤 3：实现按 code 获取配置和缓存**

新增 `get_config_by_code()` 与 `get_chat_model_by_code()`。缓存键包含：

```python
(profile.value, config.id, config.updated_at, prompt_version, "explicit")
```

为 `GRADING_STRUCTURER` 增加低温、短超时档位：

```python
ModelProfile.GRADING_STRUCTURER: {
    "temperature": 0.0,
    "max_tokens": 4000,
    "timeout": 20,
},
```

动态批改模型不沿用当前 120 秒请求超时：主批改与独立复核的每次底层请求统一设为 35 秒，结构化模型每次请求设为 20 秒。Celery 批改任务维持 `soft_time_limit=120`、`time_limit=150`；陈旧 Run 的读取时收口阈值固定为 180 秒。这样独立结构化路径即使触发一次结构化修复，底层请求上限仍为 `35 + 35 + 20 + 20 = 110` 秒，并为软超时前的解析和数据库落库保留 10 秒。

- [ ] **步骤 4：实现动态批改 Agent 工厂**

在注册表增加方法 `get_grading_agent(self, db: Session, *, model_code: str, reviewer: bool, structured: bool)`。它先通过 `get_chat_model_by_code()` 获取指定 code 的模型，再根据 `reviewer` 选择主批改或独立复核系统提示；`structured=False` 时传入 `response_format=None`，`structured=True` 时传入对应契约。缓存键必须加入 `model_code`、`reviewer` 和 `structured`，防止普通文本 Agent 与结构化 Agent 互相复用。

- [ ] **步骤 5：运行路由测试并确认绿灯**

运行同一测试文件，预期全部 PASS。

- [ ] **步骤 6：提交任务 3**

```powershell
git add backend_python/app/agent/gateway.py backend_python/app/agent/registry.py backend_python/tests/unit/agent/test_grading_model_routing.py
git commit -m "fix: route grading through ai rule model"
```

## 任务 4：先用测试锁定直接结构化路径的调用上限

**文件：**
- 修改：`backend_python/app/agent/subagents/grading.py`
- 修改：`backend_python/app/agent/subagents/grading_review.py`
- 修改：`backend_python/tests/unit/agent/test_grading_repair_retry.py`
- 修改：`backend_python/tests/integration/agent/test_grading_degradation.py`

- [ ] **步骤 1：增加缺失工具调用的回归测试**

构造始终返回普通文本、不产生结构化工具调用的假模型，通过真实 `create_agent()` 执行，记录底层模型调用次数。预期：

```python
result = invoke_structured_grader(agent, state, reviewer=False)
assert result["grading_failure"]["stage"] == GRADING_AGENT_NODE
assert fake_model.call_count <= 2
```

再覆盖非法工具参数，同样最多 2 次。测试必须在旧实现下失败，证明捕获当前 `recursion_limit=9999` 回归。

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_repair_retry.py -q
```

预期因调用次数超过 2、超时或 `GraphRecursionError` 未收口而 FAIL。

- [ ] **步骤 3：实现有限结构化调用**

直接路径调用统一使用：

```python
agent.invoke(
    {"messages": messages},
    config={"recursion_limit": 2},
)
```

捕获 `GraphRecursionError`、LangChain 结构化错误和 Pydantic 校验错误，转换成有限 `grading_failure`。删除与 LangChain 内部修复重复的外层无界循环；预算每次进入 Agent 前消费，并在返回后再次校验剩余时间。

- [ ] **步骤 4：运行直接路径测试并确认绿灯**

运行相关单元和降级测试，预期全部 PASS，且调用次数断言成立。

- [ ] **步骤 5：提交任务 4**

```powershell
git add backend_python/app/agent/subagents/grading.py backend_python/app/agent/subagents/grading_review.py backend_python/tests/unit/agent/test_grading_repair_retry.py backend_python/tests/integration/agent/test_grading_degradation.py
git commit -m "fix: bound direct grading structured output retries"
```

## 任务 5：实现独立结构化模型路径

**文件：**
- 创建：`backend_python/app/agent/subagents/grading_structurer.py`
- 修改：`backend_python/app/agent/graphs/grading.py`
- 修改：`backend_python/app/agent/subagents/grading.py`
- 修改：`backend_python/app/agent/subagents/grading_review.py`
- 修改：`backend_python/tests/unit/agent/test_grading_workflow.py`
- 创建：`backend_python/tests/unit/agent/test_grading_structurer.py`

- [ ] **步骤 1：编写失败的普通报告节点测试**

假的普通文本 Agent 返回 `AIMessage(content="主批改报告正文")`，断言主节点和复核节点分别返回：

```python
assert primary_result == {
    "grading_report": "主批改普通报告",
    "usage": {"total_tokens": 120},
}
assert review_result == {
    "review_report": "独立复核普通报告",
    "usage": {"total_tokens": 110},
}
```

断言普通模式只调用一次模型且没有 `response_format`。

- [ ] **步骤 2：编写失败的结构化节点测试**

结构化节点接收教师规则、量表和两份报告，返回 `GradingReportPair`。测试检查传给结构化模型的消息不包含 base64 图片、附件路径或原始正文，只包含两份报告和规则。

无 `structured_response`、`extraction_errors` 非空、维度不匹配或分数越界均返回 `grading_failure`。

- [ ] **步骤 3：运行测试并确认红灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_structurer.py backend_python/tests/unit/agent/test_grading_workflow.py -q
```

预期 FAIL，因为普通报告字段和结构化节点不存在。

- [ ] **步骤 4：实现普通报告提取**

从 Agent 结果最后一个 `AIMessage` 提取非空文本；空文本直接返回有限失败。普通报告 Prompt 明确：教师规则是唯一评分依据；不要输出工具调用；完整给出得分依据、扣分和建议，供后续只读整理。

- [ ] **步骤 5：实现双报告结构化节点**

结构化系统 Prompt 必须包含：

```text
你只能整理两份已有批改报告，禁止读取不存在的原始作业，禁止重新评分，
禁止补造分数、证据或扣分理由。报告信息不足时写入 extraction_errors。
```

一次调用返回 `GradingReportPair`，调用配置 `recursion_limit=2`。成功后分别执行 `validate_against(rubric)`。

- [ ] **步骤 6：给批改图增加可选结构化节点**

状态增加：

```python
grading_report: str
review_report: str
structurer_enabled: bool
```

复核完成后的条件边：开启则进入 `grading_structurer`，关闭则直接进入 `grading_decision`。任一节点产生 `grading_failure` 都短路 END。

- [ ] **步骤 7：运行测试并确认绿灯**

运行任务 5 的两个测试文件，预期全部 PASS。

- [ ] **步骤 8：提交任务 5**

```powershell
git add backend_python/app/agent/graphs/grading.py backend_python/app/agent/subagents/grading.py backend_python/app/agent/subagents/grading_review.py backend_python/app/agent/subagents/grading_structurer.py backend_python/tests/unit/agent/test_grading_workflow.py backend_python/tests/unit/agent/test_grading_structurer.py
git commit -m "feat: add optional grading structurer workflow"
```

## 任务 6：任务层选择双路径并按模型记录产物与用量

**文件：**
- 修改：`backend_python/app/tasks/grading.py`
- 修改：`backend_python/tests/integration/agent/test_grading_jobs.py`
- 修改：`backend_python/tests/integration/agent/test_run_usage_persistence.py`

- [ ] **步骤 1：编写失败的双路径集成测试**

关闭绑定时断言工作流收到：

```python
{
    "rule_model_code": "mimo",
    "structurer_enabled": False,
    "structurer_model_code": None,
}
```

开启并绑定 `deepseek` 时断言：

```python
{
    "rule_model_code": "mimo",
    "structurer_enabled": True,
    "structurer_model_code": "deepseek",
}
```

切换默认模型后仍必须保持上述 code。结构化绑定无效时任务在模型调用前受控失败。

- [ ] **步骤 2：编写失败的产物与用量测试**

开启路径完成后断言 Run 同时存在 `grading_raw_reports` 和 `grading_outcome`。用量分别累加到 MiMo 和 DeepSeek，不能全部写入默认模型。

- [ ] **步骤 3：运行测试并确认红灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/integration/agent/test_grading_jobs.py backend_python/tests/integration/agent/test_run_usage_persistence.py -q
```

预期 FAIL，因为任务层尚未读取绑定或按 code 统计。

- [ ] **步骤 4：构造显式运行配置**

从作业快照读取 `modelType`，从管理员绑定读取结构化配置，并传入 `build_grading_state()`。缺少规则模型时返回稳定错误码，例如 `AGENT_RULE_MODEL_NOT_CONFIGURED`；禁止调用 `get_default_config()`。

- [ ] **步骤 5：保存原始报告产物**

只有开启路径保存：

```python
{
    "artifact_type": "grading_raw_reports",
    "schema_version": "v1",
    "payload": {
        "primary": graph_result["grading_report"],
        "review": graph_result["review_report"],
        "rule_model_code": rule_model_code,
        "structurer_model_code": structurer_model_code,
    },
}
```

产物不得包含 API Key、Base URL 或附件本地路径。

- [ ] **步骤 6：按模型拆分用量**

图状态返回按模型 code 聚合的用量映射：

```python
model_usage = {
    "mimo": {"calls": 2, "total_tokens": 1200},
    "deepseek": {"calls": 1, "total_tokens": 300},
}
```

任务层逐项调用 `increment_usage()`。

- [ ] **步骤 7：运行测试并确认绿灯**

运行任务 6 的集成测试，预期全部 PASS。

- [ ] **步骤 8：提交任务 6**

```powershell
git add backend_python/app/tasks/grading.py backend_python/tests/integration/agent/test_grading_jobs.py backend_python/tests/integration/agent/test_run_usage_persistence.py
git commit -m "feat: dispatch grading through configured output path"
```

## 任务 7：收口软硬超时与历史僵尸 Run

**文件：**
- 创建：`backend_python/app/tasks/grading_request.py`
- 修改：`backend_python/app/tasks/grading.py`
- 修改：`backend_python/app/crud/agent_run.py`
- 修改：`backend_python/app/routers/assistant.py`
- 修改：`backend_python/tests/integration/agent/test_grading_degradation.py`
- 修改：`backend_python/tests/integration/agent/test_grading_jobs.py`

- [ ] **步骤 1：编写失败的硬超时父进程测试**

构造 active `AgentRun`，调用可独立测试的收口函数：

```python
mark_grading_timeout_from_request({
    "run_id": run.id,
    "user_id": student.id,
})
assistant_db.refresh(run)
assert run.status == "failed"
assert run.error_code == AGENT_GRADING_TIMEOUT
```

重复调用必须幂等；completed/cancelled 不得被覆盖。

- [ ] **步骤 2：编写失败的陈旧 Run 测试**

`processing` 且 `started_at` 早于数据库当前时间 180 秒的 grading Run 应被收口；180 秒以内的新鲜 processing、其他 intent、running 和 completed 均保持原状。

- [ ] **步骤 3：运行测试并确认红灯**

运行降级和任务测试，预期 FAIL，当前硬超时只存在子进程异常处理。

- [ ] **步骤 4：实现 Celery Request**

继承 `celery.worker.request.Request`：

```python
class GradingTaskRequest(Request):
    def on_timeout(self, soft, timeout):
        super().on_timeout(soft, timeout)
        if not soft:
            mark_grading_timeout_from_request(self.kwargs)
```

创建任务基类并让 `run_grading_task` 使用它。收口函数自行创建/关闭 `AssistantSessionLocal`，捕获并记录清理异常，不能遮盖 Celery 原始失败。

- [ ] **步骤 5：实现陈旧 Run 收口**

CRUD 使用数据库时间边界，只更新 `intent="grading" AND status="processing"` 的目标行，并写入 `finished_at` 与 `AGENT_GRADING_TIMEOUT`。`GET /assistant/runs/{id}` 在归属校验后调用该函数再刷新实体。

- [ ] **步骤 6：运行测试并确认绿灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/integration/agent/test_grading_degradation.py backend_python/tests/integration/agent/test_grading_jobs.py -q
```

预期全部 PASS。

- [ ] **步骤 7：提交任务 7**

```powershell
git add backend_python/app/tasks/grading_request.py backend_python/app/tasks/grading.py backend_python/app/crud/agent_run.py backend_python/app/routers/assistant.py backend_python/tests/integration/agent/test_grading_degradation.py backend_python/tests/integration/agent/test_grading_jobs.py
git commit -m "fix: finalize grading runs after worker timeouts"
```

## 任务 8：补齐 AI 规则快照满分

**文件：**
- 修改：`frontend/src/api/ai-rule.ts`
- 修改：`frontend/src/views/teacher/assignments/components/AiRuleSelector.vue`
- 修改：`frontend/src/views/teacher/assignments/assigmentsEidt/index.vue`
- 创建：`frontend/src/views/teacher/assignments/components/__tests__/AiRuleSelector.spec.ts`
- 修改：`backend_python/tests/unit/test_student_submission_detail.py`

- [ ] **步骤 1：编写失败的规则快照测试**

选择 `maxScore: 60` 的规则并断言组件 emit：

```ts
expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual({
  id: "9",
  name: "实验报告规则",
  modelType: "mimo",
  prompt: "按实验要求评分",
  maxScore: 60,
});
```

后端旧快照无 `maxScore` 时仍返回 100，新快照返回保存值。

- [ ] **步骤 2：运行前后端测试并确认红灯**

```powershell
cd frontend
npm test -- --run src/views/teacher/assignments/components/__tests__/AiRuleSelector.spec.ts
cd ..
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/test_student_submission_detail.py -q
```

- [ ] **步骤 3：补齐类型和快照字段**

所有 AI 规则读取、表单状态和作业提交 DTO 均保留 `maxScore`。旧数据仍通过 `rule.maxScore ?? 100` 兼容，不做破坏性数据迁移。

- [ ] **步骤 4：运行测试并确认绿灯**

运行同一组命令，预期全部 PASS。

- [ ] **步骤 5：提交任务 8**

```powershell
git add frontend/src/api/ai-rule.ts frontend/src/views/teacher/assignments/components/AiRuleSelector.vue frontend/src/views/teacher/assignments/assigmentsEidt/index.vue frontend/src/views/teacher/assignments/components/__tests__/AiRuleSelector.spec.ts backend_python/tests/unit/test_student_submission_detail.py
git commit -m "fix: preserve ai rule maximum score snapshot"
```

## 任务 9：实现管理员端开关、模型选择和能力测试

**文件：**
- 修改：`backend_python/app/crud/ai_model.py`
- 修改：`backend_python/app/routers/ai_models.py`
- 修改：`frontend/src/api/ai-models.ts`
- 修改：`frontend/src/views/system/ai_model/index.vue`
- 创建：`frontend/src/views/system/ai_model/__tests__/GradingStructurerSettings.spec.ts`
- 修改：`backend_python/tests/unit/agent/test_grading_structurer_config.py`

- [ ] **步骤 1：编写失败的能力测试后端测试**

mock 结构化 Agent，成功时返回固定最小 `GradingReportPair`，失败时抛结构化异常。断言 API 只使用管理员选中的模型，不读取学生数据，并返回：

```json
{
  "success": true,
  "modelCode": "deepseek",
  "message": "结构化输出能力验证通过"
}
```

测试失败时绑定状态保持不变。

- [ ] **步骤 2：编写失败的管理员组件测试**

mock API 后断言：

```ts
expect(wrapper.get('[data-testid="structurer-enabled"]').exists()).toBe(true);
await wrapper.get('[data-testid="structurer-enabled"]').setValue(true);
expect(wrapper.get('[data-testid="structurer-model-select"]').exists()).toBe(true);
expect(wrapper.get('[data-testid="structurer-save"]').attributes("disabled")).toBeDefined();
```

选择模型并通过能力测试后才允许保存；关闭时无需选择模型；保存失败恢复服务端状态并显示错误。

- [ ] **步骤 3：运行测试并确认红灯**

运行新后端测试和 Vitest，预期因端点/组件不存在而 FAIL。

- [ ] **步骤 4：实现能力测试端点**

增加 `POST /admin/ai-models/{code}/test-structured-output`，使用固定无业务数据 Prompt 和同一 `GradingReportPair` Schema，配置 `recursion_limit=2`。只返回成功、耗时和错误摘要，不返回模型原始输出。

- [ ] **步骤 5：扩展前端 API 类型**

增加：

```ts
export interface GradingStructurerConfig {
  enabled: boolean;
  modelCode: string | null;
  model: AiModel | null;
}
```

以及 `getGradingStructurerConfig()`、`updateGradingStructurerConfig()`、`testStructuredOutput(code)`。

- [ ] **步骤 6：实现管理员配置卡片**

在模型配置页顶部增加独立卡片，不改变现有 DeepSeek/MiMo 标签内容。开关开启后从 active 模型中选择；API Key、模型名和 Base URL 仍跳转/复用已有编辑区域。测试通过状态只在当前模型 code 和 `updatedAt` 未变化时有效。

- [ ] **步骤 7：运行测试并确认绿灯**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_structurer_config.py -q
cd frontend
npm test -- --run src/views/system/ai_model/__tests__/GradingStructurerSettings.spec.ts
```

预期全部 PASS。

- [ ] **步骤 8：提交任务 9**

```powershell
git add backend_python/app/crud/ai_model.py backend_python/app/routers/ai_models.py backend_python/tests/unit/agent/test_grading_structurer_config.py frontend/src/api/ai-models.ts frontend/src/views/system/ai_model/index.vue frontend/src/views/system/ai_model/__tests__/GradingStructurerSettings.spec.ts
git commit -m "feat: manage grading structurer from admin console"
```

## 任务 10：学生端显示真实运行终态

**文件：**
- 修改：`frontend/src/api/assistant.ts`
- 修改：`frontend/src/views/student/submissions/composables/useSubmissionManagement.ts`
- 修改：`frontend/src/views/student/submissions/components/ReviewResults.vue`
- 修改：`frontend/src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts`
- 修改：`frontend/src/views/student/submissions/components/__tests__/ReviewResults.spec.ts`

- [ ] **步骤 1：编写失败的状态测试**

组合式函数加载 `getRun()` 后必须暴露：

```ts
expect(management.gradingRun.value).toMatchObject({
  status: "failed",
  errorCode: "AGENT_GRADING_TIMEOUT",
});
```

组件分别断言：

```ts
expect(failedWrapper.text()).toContain("AI 批改失败");
expect(failedWrapper.text()).toContain("等待教师人工批改");
expect(failedWrapper.text()).not.toContain("AI 智能评价中");
expect(cancelledWrapper.text()).toContain("AI 批改已取消");
```

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
cd frontend
npm test -- --run src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts src/views/student/submissions/components/__tests__/ReviewResults.spec.ts
```

预期 FAIL，当前状态只保存在内部字符串且组件不知道 Run 失败。

- [ ] **步骤 3：暴露完整 Run 摘要**

把 `gradingRunStatus` 改为包含 `status`、`errorCode`、`finalOutput` 的只读对象，并传给 `ReviewResults`。`failed/cancelled` 都终止轮询；网络错误不伪造失败。

- [ ] **步骤 4：实现持久终态 UI**

评价摘要优先级：教师结果 > AI 结果 > Run 失败/取消 > 进行中。失败卡片显示稳定用户文案，不展示内部堆栈；轮询达到上限后显示“暂未取得最终状态，请稍后刷新”，而不是继续写“评价中”。

- [ ] **步骤 5：运行测试并确认绿灯**

运行任务 10 测试，预期全部 PASS。

- [ ] **步骤 6：提交任务 10**

```powershell
git add frontend/src/api/assistant.ts frontend/src/views/student/submissions/composables/useSubmissionManagement.ts frontend/src/views/student/submissions/components/ReviewResults.vue frontend/src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts frontend/src/views/student/submissions/components/__tests__/ReviewResults.spec.ts
git commit -m "fix: show terminal grading run state to students"
```

## 任务 11：完整回归、容器验证与真实双路径验收

**文件：**
- 验证：`backend_python/`
- 验证：`frontend/`
- 验证：`docker-compose.yml`

- [ ] **步骤 1：运行批改专项后端测试**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests/unit/agent/test_grading_contracts.py backend_python/tests/unit/agent/test_grading_review_contracts.py backend_python/tests/unit/agent/test_grading_repair_retry.py backend_python/tests/unit/agent/test_grading_workflow.py backend_python/tests/unit/agent/test_grading_structurer.py backend_python/tests/unit/agent/test_grading_structurer_config.py backend_python/tests/unit/agent/test_grading_model_routing.py backend_python/tests/integration/agent/test_grading_jobs.py backend_python/tests/integration/agent/test_grading_degradation.py backend_python/tests/integration/agent/test_run_usage_persistence.py backend_python/tests/security/agent/test_ai_model_access.py -q
```

预期 0 failures。

- [ ] **步骤 2：运行完整后端测试和语法检查**

```powershell
D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests -q
D:\miniforge\envs\scientific_research\python.exe -m compileall -q backend_python/app
```

预期两条命令退出码均为 0。

- [ ] **步骤 3：运行前端专项测试**

```powershell
cd frontend
npm test -- --run src/views/system/ai_model/__tests__/GradingStructurerSettings.spec.ts src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts src/views/student/submissions/components/__tests__/ReviewResults.spec.ts src/views/teacher/assignments/components/__tests__/AiRuleSelector.spec.ts
```

预期全部 PASS。

- [ ] **步骤 4：运行完整前端测试、类型检查和构建**

```powershell
cd frontend
npm test
npx vue-tsc --noEmit
npm run build-only
```

预期全部退出码为 0。保留用户已有的 `SubmissionForm.vue`、对应测试和 `nginx.conf` 修改，不覆盖或混入本功能提交。

- [ ] **步骤 5：检查差异质量**

```powershell
git diff --check
git status --short
```

预期无空白错误；工作区只包含计划内变更和任务开始前已存在的用户修改。

- [ ] **步骤 6：重建后端与 Worker**

```powershell
docker compose --env-file .env.docker up -d --build backend worker frontend
docker ps --format "table {{.Names}}\t{{.Status}}"
```

预期 MySQL/PostgreSQL/Redis 健康，backend、worker、frontend 正常运行。

- [ ] **步骤 7：验收关闭独立结构化模型路径**

1. 管理员关闭开关。
2. 创建/选择支持结构化输出的 AI 规则模型。
3. 提交包含 DOCX 和图片的作业。
4. 观察 Worker：每个 Agent 底层请求不超过 2 次。
5. 验证结果落库并显示；切换默认模型后仍使用 `aiRule.modelType`。
6. 使用不支持结构化输出的规则模型复测，确认有限失败、Run 为 failed/受控转人工，页面不永久转圈。

- [ ] **步骤 8：验收开启独立结构化模型路径**

1. 管理员选择 DeepSeek 或其他通过能力测试的模型并开启开关。
2. AI 规则选择 MiMo，多模态提交保持相同。
3. Worker 日志应显示两次 MiMo 普通报告调用和一次结构化模型调用，不出现无限 model 自循环。
4. `grading_raw_reports` 与 `grading_outcome` 产物存在且不含密钥/本地路径。
5. 教师端分维度产物、学生端分数和人工复核提示正常。

- [ ] **步骤 9：验收硬超时收口**

用测试配置让模型调用超过 hard limit，确认：Celery Result 为 FAILURE、AgentRun 为 `failed/AGENT_GRADING_TIMEOUT`、学生页面显示失败并停止轮询。恢复正常配置后再提交一次，确认新版本任务不受旧 Run 影响。

- [ ] **步骤 10：提交必要的验收修正**

若验收发现计划范围内问题，先补失败测试，再做最小修复并重新执行对应验证。没有修正时不创建空提交。

## 实施完成定义

- [ ] 管理员可以开启、关闭并唯一选择结构化模型。
- [ ] 能力测试失败时不能启用结构化绑定。
- [ ] 关闭路径严格使用 AI 规则模型直接结构化，且调用有上限。
- [ ] 开启路径严格执行“两次规则模型普通报告 + 一次结构化模型”。
- [ ] 教师 Prompt、模型选择和满分快照均被忠实使用。
- [ ] 模型用量按实际模型分别记录。
- [ ] 软超时、硬超时和历史陈旧 Run 均进入终态。
- [ ] 学生端不会把 failed/cancelled/轮询耗尽继续显示为“评价中”。
- [ ] 后端完整测试、前端完整测试、类型检查、构建和容器验收全部通过。
