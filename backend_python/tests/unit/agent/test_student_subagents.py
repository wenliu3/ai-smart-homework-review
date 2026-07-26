import json

from langchain_core.messages import ToolMessage

from app.agent.contracts import ReviewResult, StudentIntent, StudentIntentDecision
from app.agent.subagents import (
    feedback_explainer,
    learning_coach,
    learning_planner,
    student_final_reviewer,
)


class _Agent:
    def __init__(self, structured, messages=None):
        self.structured = structured
        self.messages = messages or []
        self.contexts = []

    def invoke(self, payload, context=None):
        self.contexts.append(context)
        return {
            "structured_response": self.structured,
            "messages": self.messages,
        }


class _Registry:
    def __init__(self, agents):
        self.agents = agents

    def get_specialist(self, name, db):
        return self.agents[name]


def _state():
    return {
        "actor": type("Actor", (), {"user_id": 7})(),
        "user_message": "解释我的反馈",
        "recent_messages": [],
        "intent": StudentIntentDecision(
            intent=StudentIntent.FEEDBACK_EXPLANATION,
            target_agent="feedback_explainer",
        ),
    }


def test_three_student_specialists_use_student_context_and_verified_tool_evidence():
    tool_message = ToolMessage(
        content=json.dumps({
            "evidence_refs": [
                "mysql://submissions/1?scope=current_student",
            ],
        }),
        tool_call_id="call-1",
    )
    agents = {
        name: _Agent({
            "answer": f"{name} answer",
            "evidence_refs": [
                "mysql://submissions/1?scope=current_student",
                "model://invented",
            ],
            "limitations": [],
        }, [tool_message])
        for name in ("learning_coach", "feedback_explainer", "learning_planner")
    }
    registry = _Registry(agents)

    updates = [
        learning_coach.create_node(object(), registry)(_state()),
        feedback_explainer.create_node(object(), registry)(_state()),
        learning_planner.create_node(object(), registry)(_state()),
    ]

    assert all(update["evidence_refs"] == [
        "mysql://submissions/1?scope=current_student",
    ] for update in updates)
    assert all(agent.contexts[0].student_id == 7 for agent in agents.values())


def test_student_reviewer_allows_prohibited_safety_response_without_evidence():
    reviewer = _Agent({"approved": True, "issues": []})
    registry = _Registry({"student_final_reviewer": reviewer})
    state = {
        **_state(),
        "intent": StudentIntentDecision(
            intent=StudentIntent.PROHIBITED_ANSWER,
            target_agent="prohibited_answer",
        ),
        "candidate_answer": "我不能代写，但可以提供思路。",
        "evidence_refs": [],
    }

    update = student_final_reviewer.create_node(object(), registry)(state)

    assert update["review"] == ReviewResult(approved=True)
