"""最终审核 Agent 必须使用结构化输出并在异常时失败关闭。"""

from langchain_core.messages import AIMessage

from app.agent.contracts import (
    ActorContext,
    IntentDecision,
    ReviewResult,
    TeacherIntent,
)
from app.agent.subagents.final_reviewer import create_node


class _FakeAgent:
    def __init__(self, result):
        self._result = result

    def invoke(self, *args, **kwargs):
        return self._result


class _FakeRegistry:
    def __init__(self, result):
        self._agent = _FakeAgent(result)

    def get_specialist(self, name, db):
        assert name == "final_reviewer"
        return self._agent


def _state():
    return {
        "actor": ActorContext(
            user_id=7,
            role="teacher",
            request_id="req-review",
            session_id="session-review",
        ),
        "candidate_answer": "当前有 2 个班级。",
        "evidence_refs": ["mysql://classes?scope=current_teacher"],
    }


def test_reviewer_rejects_when_structured_response_is_missing():
    node = create_node(db=object(), registry=_FakeRegistry({
        "messages": [AIMessage(content="not json")],
    }))

    review = node(_state())["review"]

    assert review.approved is False
    assert review.issues


def test_reviewer_rejects_string_boolean_in_structured_response():
    node = create_node(db=object(), registry=_FakeRegistry({
        "messages": [AIMessage(content='{"approved":"false","issues":[]}')],
        "structured_response": {"approved": "false", "issues": []},
    }))

    review = node(_state())["review"]

    assert review.approved is False
    assert review.issues


def test_reviewer_accepts_valid_review_result():
    expected = ReviewResult(approved=True, issues=[])
    node = create_node(db=object(), registry=_FakeRegistry({
        "messages": [AIMessage(content="审核完成")],
        "structured_response": expected,
    }))

    review = node(_state())["review"]

    assert review == expected


def test_reviewer_rejects_factual_answer_without_evidence_before_model_call():
    registry = _FakeRegistry({
        "messages": [AIMessage(content="不应调用")],
        "structured_response": ReviewResult(approved=True, issues=[]),
    })
    node = create_node(db=object(), registry=registry)
    state = _state()
    state["evidence_refs"] = []

    review = node(state)["review"]

    assert review.approved is False
    assert "证据" in review.issues[0]


class _RecordingAgent:
    """记录发给模型的 prompt，便于断言审核要点按意图切换。"""

    def __init__(self, result):
        self._result = result
        self.prompts: list[str] = []

    def invoke(self, payload, **kwargs):
        self.prompts.append(payload["messages"][-1].content)
        return self._result


class _RecordingRegistry:
    def __init__(self, agent):
        self._agent = agent

    def get_specialist(self, name, db):
        assert name == "final_reviewer"
        return self._agent


def test_reviewer_swaps_write_rule_for_action_draft_intent():
    """ACTION_DRAFT 的候选回答必然要描述「已起草待审批操作」——
    审核红线必须换成「不得声称已执行/将自动执行」，否则真实模型
    会按字面把整条写操作闭环全部拒掉（真实环境已复现）。"""
    agent = _RecordingAgent({
        "messages": [AIMessage(content="审核完成")],
        "structured_response": ReviewResult(approved=True, issues=[]),
    })
    node = create_node(db=object(), registry=_RecordingRegistry(agent))
    state = _state()
    state.update({
        "candidate_answer": "已为您起草发布作业《计算机发展史小论文》的操作草案。",
        "intent": IntentDecision(
            intent=TeacherIntent.ACTION_DRAFT,
            target_agent="teacher_action",
        ),
    })

    review = node(state)["review"]

    assert review.approved is True
    prompt = agent.prompts[-1]
    assert "不包含或暗示可以执行写操作" not in prompt
    assert "待审批" in prompt
    assert "声称操作已经执行" in prompt


def test_reviewer_keeps_write_rule_for_readonly_intents():
    agent = _RecordingAgent({
        "messages": [AIMessage(content="审核完成")],
        "structured_response": ReviewResult(approved=True, issues=[]),
    })
    node = create_node(db=object(), registry=_RecordingRegistry(agent))
    state = _state()
    state["intent"] = IntentDecision(
        intent=TeacherIntent.TEACHING_DATA,
        target_agent="teaching_data",
    )

    node(state)

    assert "不包含或暗示可以执行写操作" in agent.prompts[-1]


def test_reviewer_allows_casual_chat_without_business_evidence():
    node = create_node(db=object(), registry=_FakeRegistry({
        "messages": [AIMessage(content="审核完成")],
        "structured_response": ReviewResult(approved=True, issues=[]),
    }))
    state = _state()
    state.update({
        "candidate_answer": "你好，我是 AI 教学助手。",
        "evidence_refs": [],
        "intent": IntentDecision(
            intent=TeacherIntent.CASUAL_CHAT,
            target_agent="casual_chat",
        ),
    })

    review = node(state)["review"]

    assert review.approved is True
