"""学生/管理员 Subagent 结构化输出降级回归。

LLM 输出缺失或不合规时必须优雅降级（对齐教师端 teacher_data / final_reviewer
的模式），不得让整轮运行崩溃为 AGENT_CHAT_ERROR：
- 专业 Agent：候选回答置空 + 降级说明，交由最终审核安全拒绝。
- 最终审核 Agent：直接安全拒绝。
"""
import pytest

from app.agent.contracts import (
    AdminIntent,
    AdminIntentDecision,
    StudentIntent,
    StudentIntentDecision,
)
from app.agent.subagents import (
    admin_final_reviewer,
    audit_analysis,
    feedback_explainer,
    learning_coach,
    learning_planner,
    model_governance,
    operations_analysis,
    student_final_reviewer,
)
from app.agent.subagents.messages import (
    STRUCTURED_RESPONSE_FALLBACK_LIMITATION,
)


class _Agent:
    def __init__(self, result):
        self.result = result

    def invoke(self, payload, context=None):
        return self.result


class _Registry:
    def __init__(self, agent):
        self.agent = agent

    def get_specialist(self, name, db):
        return self.agent


def _student_state():
    return {
        "actor": type("Actor", (), {"user_id": 7})(),
        "user_message": "解释我的反馈",
        "recent_messages": [],
        "intent": StudentIntentDecision(
            intent=StudentIntent.FEEDBACK_EXPLANATION,
            target_agent="feedback_explainer",
        ),
    }


def _admin_state():
    return {
        "actor": type("Actor", (), {"user_id": 1})(),
        "user_message": "分析平台运行情况",
        "recent_messages": [],
        "intent": AdminIntentDecision(
            intent=AdminIntent.OPERATIONS_ANALYSIS,
            target_agent="operations_analysis",
        ),
    }


# 三类不合规输出：缺键 / 类型不合规 / 字段校验失败
_INVALID_RESULTS = (
    {"messages": []},
    {"structured_response": None, "messages": []},
    {"structured_response": {"answer": ""}, "messages": []},
)


@pytest.mark.parametrize("result", _INVALID_RESULTS)
@pytest.mark.parametrize(
    ("module", "state_factory"),
    [
        (learning_coach, _student_state),
        (feedback_explainer, _student_state),
        (learning_planner, _student_state),
        (operations_analysis, _admin_state),
        (audit_analysis, _admin_state),
        (model_governance, _admin_state),
    ],
)
def test_specialists_degrade_gracefully_on_invalid_structured_output(
    module, state_factory, result,
):
    node = module.create_node(object(), _Registry(_Agent(result)))

    update = node(state_factory())

    assert update["candidate_answer"] == ""
    assert update["evidence_refs"] == []
    assert STRUCTURED_RESPONSE_FALLBACK_LIMITATION in update["limitations"]
    assert "specialist_response" not in update


@pytest.mark.parametrize("result", _INVALID_RESULTS)
@pytest.mark.parametrize(
    ("module", "state_factory"),
    [
        (student_final_reviewer, _student_state),
        (admin_final_reviewer, _admin_state),
    ],
)
def test_final_reviewers_reject_safely_on_invalid_structured_output(
    module, state_factory, result,
):
    node = module.create_node(object(), _Registry(_Agent(result)))
    state = {
        **state_factory(),
        "candidate_answer": "候选回答",
        "evidence_refs": ["mysql://evidence/1"],
    }

    update = node(state)

    assert update["review"].approved is False
    assert update["review"].issues == ["审核模型未返回有效的结构化结果"]
