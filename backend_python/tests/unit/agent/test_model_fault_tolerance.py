"""模型容错（规划阶段 4.2）。

- 网关构造的模型自带一次瞬时错误重试。
- 模型超时异常映射为稳定错误码 AGENT_MODEL_TIMEOUT（不泄露内部细节）。
- 剩余预算不足时不再发起模型调用（按 RunBudget.remaining_seconds 收紧）。
"""
import httpx
import pytest

from app.agent.contracts import AGENT_MODEL_TIMEOUT, ReviewResult
from app.agent.gateway import ModelGateway
from app.agent.contracts import ModelProfile
from app.agent.runtime import BudgetExceeded, RunBudget, is_model_timeout
from app.agent.service import orchestrate_teacher_run
from app.crud.agent_session import create_session
from app.models import AgentRun


def test_chat_model_retries_transient_errors_once(db, ai_model_factory):
    ai_model_factory()

    llm = ModelGateway().get_chat_model(
        db, ModelProfile.GENERAL, prompt_version="v1",
    )

    assert llm.max_retries == 1


def test_is_model_timeout_recognizes_timeout_families():
    import openai

    request = httpx.Request("POST", "https://api.test/v1")
    assert is_model_timeout(openai.APITimeoutError(request=request))
    assert is_model_timeout(httpx.ReadTimeout("read timed out"))
    assert not is_model_timeout(ValueError("其他错误"))
    assert not is_model_timeout(RuntimeError("connection reset"))


class _TimeoutSpecialists:
    def teaching_data(self, state):
        import openai

        raise openai.APITimeoutError(
            request=httpx.Request("POST", "https://api.test/v1"),
        )

    def teaching_strategy(self, state):
        return {"candidate_answer": "x"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


def test_model_timeout_maps_to_stable_error_code(assistant_db):
    session = create_session(
        assistant_db, user_id=7, actor_role="teacher", session_id="sesstimeout01",
    )

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-timeout-001",
        specialists=_TimeoutSpecialists(),
        assistant_db=assistant_db,
    )

    assert result.status == "failed"
    assert result.error_code == AGENT_MODEL_TIMEOUT
    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(
        AgentRun.id == result.run_id,
    ).one()
    assert run.error_code == AGENT_MODEL_TIMEOUT
    failed = [e for e in result.events if e["type"] == "run.failed"]
    assert failed[0]["data"]["error_code"] == AGENT_MODEL_TIMEOUT
    # 绝不透传异常类型与内部细节
    assert "APITimeoutError" not in str(result.events)


def test_grading_invoke_skipped_when_budget_nearly_exhausted():
    from app.agent.contracts import (
        GradingRubric, NormalizedSubmissionContent, RubricCriterion,
    )
    from app.agent.subagents.grading import invoke_with_repair

    calls = []

    class _Agent:
        def invoke(self, payload):
            calls.append(payload)
            return {}

    budget = RunBudget(max_model_calls=6, timeout_seconds=120)
    budget.started_at -= 118  # 剩余不足 5 秒

    with pytest.raises(BudgetExceeded):
        invoke_with_repair(
            _Agent(),
            {
                "rubric": GradingRubric(version="v1", criteria=[
                    RubricCriterion(
                        criterion_id="q", title="质量", max_score=100,
                    ),
                ]),
                "normalized_content": NormalizedSubmissionContent(),
                "runtime_budget": budget,
            },
            reviewer=False,
            stage="grading_agent",
        )

    assert calls == []
