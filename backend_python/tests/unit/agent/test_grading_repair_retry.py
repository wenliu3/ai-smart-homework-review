"""批改 Subagent 的结构化调用收口与降级（规划 3B.2 / 任务 4）。

- 直接结构化路径（真实 create_agent）底层模型调用锁定到最多 2 次：
  模型不产出结构化工具调用（返回普通文本）或产出非法工具参数时，
  response_format 机制会在内部反复重试，recursion_limit 默认 9999
  会形成无界模型调用——invoke_structured_grader 显式传 recursion_limit=2
  收口，并把递归上限 / 结构化输出错误 / 校验错误转换为有限 grading_failure。
- 结构化校验失败 → grading_failure（原始输出留证），不抛异常。
- 每次模型调用消费 RunBudget.model_call。
"""
import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.errors import GraphRecursionError

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    NormalizedSubmissionContent,
    RubricCriterion,
)
from app.agent.graphs.grading import GRADING_AGENT_NODE
from app.agent.runtime import BudgetExceeded, RunBudget
from app.agent.subagents.grading import (
    create_node as create_grading_node,
    invoke_structured_grader,
)
from app.agent.subagents.grading_review import create_node as create_review_node


class _SequenceAgent:
    """按调用顺序返回预设响应的替身；兼容 config= 关键字。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, payload, **kwargs):
        self.calls.append(payload)
        return self.responses[len(self.calls) - 1]


class _Registry:
    def __init__(self, agents):
        self.agents = agents

    def get_specialist(self, name, db):
        return self.agents[name]


class _BoundedPlainTextModel(BaseChatModel):
    """记录调用次数、始终返回普通文本的假模型（驱动真实 create_agent 内联循环）。

    raise_at：假模型自身抛 GraphRecursionError 的调用次数。没有 recursion_limit
    收口时 LangChain 会递归到默认 9999 次太慢，这里用 raise_at=3 快速截断，
    让「无收口」的红灯可控；核心断言是 call_count <= 2，与 raise_at 无关。
    """
    call_count: int = 0
    raise_at: int = 3
    bound_tools: list | None = None

    @property
    def _llm_type(self) -> str:
        return "bounded-plain-text-fake"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        # 结构化输出工具在模型调用时动态绑定；假模型忽略绑定，从不真正产出工具调用
        self.bound_tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.call_count += 1
        if self.raise_at is not None and self.call_count >= self.raise_at:
            raise GraphRecursionError("假模型模拟递归上限（无收口时截断重试）")
        return ChatResult(generations=[ChatGeneration(
            message=AIMessage(content="普通文本"),
        )])


class _BoundedInvalidToolModel(_BoundedPlainTextModel):
    """始终产出非法工具参数的假模型：args 无法解析为 GradingDraft。"""

    @property
    def _llm_type(self) -> str:
        return "bounded-invalid-tool-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.call_count += 1
        if self.raise_at is not None and self.call_count >= self.raise_at:
            raise GraphRecursionError("假模型模拟递归上限（无收口时截断重试）")
        name = self.bound_tools[0].name if self.bound_tools else "GradingDraft"
        return ChatResult(generations=[ChatGeneration(
            message=AIMessage(content="", tool_calls=[{
                "name": name,
                "args": {
                    "rubric_version": "v1",
                    "items": "not-a-list",
                    "summary": "非法工具参数",
                },
                "id": f"call_{self.call_count}",
                "type": "tool_call",
            }]),
        )])


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


# ========== 直接结构化路径调用上限（任务 4） ==========

def test_plain_text_model_calls_bounded_to_two():
    fake = _BoundedPlainTextModel()
    agent = create_agent(
        model=fake,
        tools=[],
        system_prompt="你是结构化批改 Agent",
        response_format=GradingDraft,
    )

    result = invoke_structured_grader(
        agent, _state(), reviewer=False, stage=GRADING_AGENT_NODE,
    )

    assert result["grading_failure"]["stage"] == GRADING_AGENT_NODE
    assert fake.call_count <= 2


def test_invalid_tool_args_model_calls_bounded_to_two():
    fake = _BoundedInvalidToolModel()
    agent = create_agent(
        model=fake,
        tools=[],
        system_prompt="你是结构化批改 Agent",
        response_format=GradingDraft,
    )

    result = invoke_structured_grader(
        agent, _state(), reviewer=False, stage=GRADING_AGENT_NODE,
    )

    assert result["grading_failure"]["stage"] == GRADING_AGENT_NODE
    assert fake.call_count <= 2


# ========== 结构化校验与降级 ==========

def test_valid_response_returns_draft():
    agent = _SequenceAgent([{"structured_response": _valid_payload()}])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    update = node(_state())

    assert len(agent.calls) == 1
    assert update["grading_draft"].total_score == 85


def test_invalid_response_degrades_to_grading_failure_not_exception():
    agent = _SequenceAgent([{"structured_response": _broken_payload()}])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    update = node(_state())

    assert len(agent.calls) == 1
    assert "grading_draft" not in update
    failure = update["grading_failure"]
    assert failure["stage"] == "grading_agent"
    assert failure["error"]
    assert "wrong_id" in failure["raw_response"]


def test_missing_structured_response_also_degrades():
    agent = _SequenceAgent([{"messages": []}])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    update = node(_state())

    assert "grading_failure" in update


def test_review_node_failure_reports_review_stage():
    agent = _SequenceAgent([{"structured_response": _broken_payload()}])
    node = create_review_node(object(), _Registry({"grading_review": agent}))

    update = node(_state())

    assert update["grading_failure"]["stage"] == "grading_review_agent"


def test_each_invoke_consumes_model_call_budget():
    budget = RunBudget(max_model_calls=6, timeout_seconds=120)
    agent = _SequenceAgent([{"structured_response": _valid_payload()}])
    node = create_grading_node(object(), _Registry({"grading": agent}))

    node(_state(budget))

    assert budget.model_call_count == 1


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
