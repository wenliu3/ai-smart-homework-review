"""Agent 契约测试：身份上下文、模型档位、用量、稳定错误码。"""
import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    AGENT_BUDGET_EXCEEDED,
    AGENT_CHAT_ERROR,
    AGENT_MODEL_TIMEOUT,
    SAFE_CHAT_ERROR_MESSAGE,
    ActorContext,
    AgentError,
    ModelProfile,
    UsageSummary,
)


def test_actor_context_valid():
    ctx = ActorContext(user_id=1, role="teacher", request_id="req-1", session_id="sess-1")
    assert ctx.user_id == 1
    assert ctx.role == "teacher"


@pytest.mark.parametrize("role", ["admin", "root", "", "TEACHER"])
def test_actor_context_rejects_invalid_role(role):
    with pytest.raises(ValidationError):
        ActorContext(user_id=1, role=role, request_id="r", session_id="s")


def test_model_profile_values():
    assert {p.value for p in ModelProfile} == {"router", "general", "vision_grader", "reviewer", "grading_structurer"}


def test_usage_summary_total_tokens():
    usage = UsageSummary(model_id=1, profile=ModelProfile.GENERAL, prompt_tokens=100, completion_tokens=50)
    assert usage.total_tokens == 150
    assert usage.latency_ms == 0


def test_agent_error_defaults_not_retryable():
    err = AgentError(code=AGENT_CHAT_ERROR, message=SAFE_CHAT_ERROR_MESSAGE)
    assert err.retryable is False


def test_error_codes_stable():
    """错误码字符串是对外协议的一部分，改动必须显式审查。"""
    assert AGENT_CHAT_ERROR == "AGENT_CHAT_ERROR"
    assert AGENT_MODEL_TIMEOUT == "AGENT_MODEL_TIMEOUT"
    assert AGENT_BUDGET_EXCEEDED == "AGENT_BUDGET_EXCEEDED"
    assert SAFE_CHAT_ERROR_MESSAGE == "AI 服务暂时不可用，请稍后重试"
