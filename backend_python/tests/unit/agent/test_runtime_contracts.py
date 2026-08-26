"""教师多智能体结构化契约与执行预算测试。"""
import pytest
from pydantic import ValidationError

from app.agent.contracts import AnalysisArtifact, EvidenceRef, ReviewResult, TeacherIntent
from app.agent.runtime import BudgetExceeded, RunBudget, default_run_budget
from app.config import settings


def test_evidence_requires_safe_reference():
    with pytest.raises(ValidationError):
        EvidenceRef(source_type="database", reference="", summary="两个班级")


def test_analysis_artifact_requires_evidence_for_metrics():
    with pytest.raises(ValidationError):
        AnalysisArtifact(title="统计", metrics={"classCount": 2}, evidence=[])


def test_review_result_requires_issues_when_rejected():
    with pytest.raises(ValidationError):
        ReviewResult(approved=False, issues=[])


def test_teacher_intent_values_are_stable():
    assert TeacherIntent.TEACHING_DATA.value == "teaching_data"
    assert TeacherIntent.TEACHING_STRATEGY.value == "teaching_strategy"
    assert TeacherIntent.UNSUPPORTED_WRITE.value == "unsupported_write"


def test_budget_rejects_extra_tool_call():
    budget = RunBudget(max_nodes=8, max_tool_calls=12, timeout_seconds=45)
    for _ in range(12):
        budget.consume_tool_call()
    with pytest.raises(BudgetExceeded):
        budget.consume_tool_call()


def test_default_run_budget_enables_all_production_limits():
    budget = default_run_budget()

    assert budget.max_nodes == 8
    assert budget.max_tool_calls == 12
    assert budget.max_model_calls == 12
    # 整轮运行超时从配置读取，默认 150s，足以容纳「工具调用→结构化草案→最终审核」
    # 多次串行模型调用；大于单次模型请求超时（40s）。
    assert budget.timeout_seconds == settings.AGENT_RUN_TIMEOUT_SECONDS
    assert budget.timeout_seconds >= 45
    assert 0 < budget.remaining_seconds <= settings.AGENT_RUN_TIMEOUT_SECONDS


def test_grading_run_budget_keeps_its_own_limits():
    """批改独立预算不受通用 AGENT_RUN_TIMEOUT_SECONDS 影响。"""
    budget = RunBudget(
        max_nodes=8,
        max_tool_calls=12,
        max_model_calls=6,
        timeout_seconds=120,
    )

    assert budget.max_model_calls == 6
    assert budget.timeout_seconds == 120


def test_default_budget_consuming_model_calls_enforces_max_model_calls():
    budget = RunBudget(max_model_calls=1, timeout_seconds=150)
    budget.consume_model_call()
    with pytest.raises(BudgetExceeded):
        budget.consume_model_call()
