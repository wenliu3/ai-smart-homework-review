# AI 助手运行预算调整实现计划

> **面向 AI 代理的工作者：** 在当前会话中按 TDD 顺序执行本计划。

**目标：** 将交互式 AI 助手的默认单次运行总预算调整为 600 秒。

**架构：** 保留现有 `RunBudget` 结构，仅修改 `default_run_budget()` 工厂返回值。通过现有运行时契约测试锁定新值，不影响模型单次请求和批改任务预算。

**技术栈：** Python、pytest

---

### 任务 1：调整默认运行预算

**文件：**
- 修改：`backend_python/tests/unit/agent/test_runtime_contracts.py`
- 修改：`backend_python/app/agent/runtime.py`

- [x] 将 `test_default_run_budget_enables_all_production_limits` 的总超时预期改为 `600`。
- [x] 运行该测试并确认因实际值仍为 `45` 而失败。
- [x] 将 `default_run_budget()` 的 `timeout_seconds` 改为 `600`。
- [x] 重新运行运行时契约测试并确认通过。
- [x] 运行后端语法检查，确认没有语法回归。
