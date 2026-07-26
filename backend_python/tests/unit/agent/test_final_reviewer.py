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
