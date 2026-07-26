"""批改 Subagent 的格式修复重试与降级（规划阶段 3B.2）。

- 结构化校验失败先把错误回喂模型重试一次。
- 重试成功照常返回草案；仍失败返回 grading_failure（原始输出留证），不抛异常。
- 每次模型调用消费 RunBudget.model_call。
"""
import pytest

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    NormalizedSubmissionContent,
    RubricCriterion,
)
from app.agent.runtime import BudgetExceeded, RunBudget
from app.agent.subagents.grading import create_node as create_grading_node
from app.agent.subagents.grading_review import create_node as create_review_node


class _SequenceAgent:
    """按调用顺序返回预设响应的替身。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        return self.responses[len(self.calls) - 1]


class _Registry:
    def __init__(self, agents):
        self.agents = agents

    def get_specialist(self, name, db):
        return self.agents[name]


def _rubric():
    return GradingRubric(
        version="v1",
        criteria=[RubricCriterion(
            criterion_id="quality", title="质量", max_score=100,
        )],
    )


def _valid_payload():
    return GradingDraft(
        rubric_version="v1",
        items=[CriterionGrade(
            criterion_id="quality",
            title="质量",
            score=85,
            max_score=100,
            feedback="完成良好",
            evidence_refs=["submission:text:1"],
        )],
        summary="总体完成良好",
    ).model_dump()


def _broken_payload():
    """criterion_id 与量表不符：pydantic 校验通过、validate_against 失败。"""
    payload = _valid_payload()
    payload["items"][0]["criterion_id"] = "wrong_id"
    return payload


def _state(budget=None):
    state = {
        "rubric": _rubric(),
        "normalized_content": NormalizedSubmissionContent(),
    }
    if budget is not None:
        state["runtime_budget"] = budget
    return state


def test_validation_failure_triggers_exactly_one_repair_retry():
    agent = _SequenceAgent([
        {"structured_response": _broken_payload()},
        {"structured_response": _valid_payload()},
    ])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    update = node(_state())

    assert len(agent.calls) == 2
    assert update["grading_draft"].total_score == 85
    # 重试消息必须携带首轮的校验错误，让模型知道要修什么
    assert "唯一对应" in str(agent.calls[1]) or "评分项" in str(agent.calls[1])


def test_double_failure_degrades_to_grading_failure_not_exception():
    agent = _SequenceAgent([
        {"structured_response": _broken_payload()},
        {"structured_response": _broken_payload()},
    ])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    update = node(_state())

    assert len(agent.calls) == 2
    assert "grading_draft" not in update
    failure = update["grading_failure"]
    assert failure["stage"] == "grading_agent"
    assert failure["error"]
    assert "wrong_id" in failure["raw_response"]


def test_missing_structured_response_also_degrades():
    agent = _SequenceAgent([
        {"messages": []},
        {"messages": []},
    ])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    update = node(_state())

    assert "grading_failure" in update


def test_review_node_failure_reports_review_stage():
    agent = _SequenceAgent([
        {"structured_response": _broken_payload()},
        {"structured_response": _broken_payload()},
    ])
    node = create_review_node(object(), _Registry({"grading_review": agent}))

    update = node(_state())

    assert update["grading_failure"]["stage"] == "grading_review_agent"


def test_each_invoke_consumes_model_call_budget():
    budget = RunBudget(max_model_calls=6, timeout_seconds=120)
    agent = _SequenceAgent([
        {"structured_response": _broken_payload()},
        {"structured_response": _valid_payload()},
    ])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    node(_state(budget))

    assert budget.model_call_count == 2


def test_exhausted_model_budget_stops_before_invoke():
    budget = RunBudget(max_model_calls=1, timeout_seconds=120)
    budget.consume_model_call()
    agent = _SequenceAgent([{"structured_response": _valid_payload()}])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    with pytest.raises(BudgetExceeded):
        node(_state(budget))

    assert agent.calls == []


# ========== 复核档位按提交是否含图动态选择（规划阶段 3B.1） ==========

def test_review_uses_vision_profile_for_image_submissions():
    from app.agent.contracts import SubmissionImageRef

    requested = []

    class _RecordingRegistry:
        def get_specialist(self, name, db):
            requested.append(name)
            return _SequenceAgent([{"structured_response": _valid_payload()}])

    content = NormalizedSubmissionContent(image_refs=[SubmissionImageRef(
        file_name="chart.png",
        file_path="D:/nonexistent/chart.png",
        evidence_ref="submission:image:1",
    )])
    node = create_review_node(object(), _RecordingRegistry())
    state = {"rubric": _rubric(), "normalized_content": content}

    # 图片文件读不到会抛错，但档位选择先于消息构造发生
    try:
        node(state)
    except OSError:
        pass

    assert requested == ["grading_review_vision"]


def test_review_uses_text_profile_for_text_only_submissions():
    requested = []

    class _RecordingRegistry:
        def get_specialist(self, name, db):
            requested.append(name)
            return _SequenceAgent([{"structured_response": _valid_payload()}])

    node = create_review_node(object(), _RecordingRegistry())
    node(_state())

    assert requested == ["grading_review"]
