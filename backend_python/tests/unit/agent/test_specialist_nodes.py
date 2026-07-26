"""专业 Agent 节点的结构化输出、证据和会话上下文测试。"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.contracts import ActorContext, ReviewResult, SpecialistResponse
from app.agent.subagents.teacher_data import create_node


class _CapturingAgent:
    def __init__(self, structured_response, tool_evidence_refs=None):
        self.structured_response = structured_response
        self.tool_evidence_refs = (
            list(structured_response.evidence_refs)
            if tool_evidence_refs is None
            else list(tool_evidence_refs)
        )
        self.messages = None

    def invoke(self, payload, **kwargs):
        self.messages = payload["messages"]
        messages = [
            ToolMessage(
                content=json.dumps({"evidence_refs": self.tool_evidence_refs}),
                tool_call_id="tool-call-1",
            ),
            AIMessage(content="模型展示文本不应作为关键状态"),
        ]
        return {
            "messages": messages,
            "structured_response": self.structured_response,
        }


class _Registry:
    def __init__(self, agent):
        self.agent = agent

    def get_specialist(self, name, db):
        assert name == "teaching_data"
        return self.agent


def _state():
    return {
        "actor": ActorContext(
            user_id=7,
            role="teacher",
            request_id="req-specialist",
            session_id="session-specialist",
        ),
        "conversation_summary": "教师正在分析一班的提交情况。",
        "recent_messages": [
            {"role": "user", "content": "先查一班"},
            {"role": "assistant", "content": "已找到一班"},
        ],
        "user_message": "他们最近提交得怎么样？",
    }


def test_specialist_uses_structured_response_as_graph_state():
    expected = SpecialistResponse(
        answer="一班最近有 12 份提交。",
        evidence_refs=["mysql://assignments?scope=current_teacher"],
    )
    agent = _CapturingAgent(expected)

    update = create_node(object(), _Registry(agent))(_state())

    assert update["candidate_answer"] == expected.answer
    assert update["evidence_refs"] == expected.evidence_refs
    assert update["specialist_response"] == expected


def test_specialist_receives_summary_recent_messages_and_current_message():
    agent = _CapturingAgent(SpecialistResponse(
        answer="回答",
        evidence_refs=["mysql://dashboard?scope=current_teacher"],
    ))

    create_node(object(), _Registry(agent))(_state())

    assert isinstance(agent.messages[0], SystemMessage)
    assert "一班" in agent.messages[0].content
    assert isinstance(agent.messages[1], HumanMessage)
    assert isinstance(agent.messages[2], AIMessage)
    assert isinstance(agent.messages[3], HumanMessage)
    assert agent.messages[3].content == "他们最近提交得怎么样？"


def test_specialist_strips_evidence_not_observed_in_tool_messages():
    response = SpecialistResponse(
        answer="伪造事实",
        evidence_refs=["mysql://forged"],
    )
    agent = _CapturingAgent(response, tool_evidence_refs=[])

    update = create_node(object(), _Registry(agent))(_state())

    assert update["evidence_refs"] == []
    assert update["specialist_response"].evidence_refs == []
    assert any("证据" in item for item in update["limitations"])


def test_revision_message_contains_candidate_and_reviewer_issues():
    agent = _CapturingAgent(SpecialistResponse(
        answer="修订回答",
        evidence_refs=["mysql://dashboard?scope=current_teacher"],
    ))
    state = _state()
    state.update({
        "revision_count": 1,
        "candidate_answer": "上一版回答",
        "review": ReviewResult(
            approved=False,
            issues=["缺少数据范围说明"],
        ),
    })

    create_node(object(), _Registry(agent))(state)

    revision = agent.messages[-1]
    assert isinstance(revision, HumanMessage)
    assert "上一版回答" in revision.content
    assert "缺少数据范围说明" in revision.content
