import json

from langchain_core.messages import ToolMessage

from app.agent.contracts import AdminIntent, AdminIntentDecision, ReviewResult
from pydantic import ValidationError
import pytest
from app.agent.subagents import (
    admin_final_reviewer,
    audit_analysis,
    model_governance,
    operations_analysis,
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
        "actor": type("Actor", (), {"user_id": 1})(),
        "user_message": "分析平台运行情况",
        "recent_messages": [],
        "intent": AdminIntentDecision(
            intent=AdminIntent.OPERATIONS_ANALYSIS,
            target_agent="operations_analysis",
        ),
    }


def test_admin_specialists_use_admin_context_and_only_verified_evidence():
    tool_message = ToolMessage(
        content=json.dumps({
            "evidence_refs": ["mysql://platform/aggregate"],
        }),
        tool_call_id="call-1",
    )
    agents = {
        name: _Agent({
            "answer": f"{name} answer",
            "evidence_refs": [
                "mysql://platform/aggregate",
                "model://invented",
            ],
            "limitations": [],
        }, [tool_message])
        for name in (
            "operations_analysis",
            "audit_analysis",
            "model_governance",
        )
    }
    registry = _Registry(agents)

    updates = [
        operations_analysis.create_node(object(), registry)(_state()),
        audit_analysis.create_node(object(), registry)(_state()),
        model_governance.create_node(object(), registry)(_state()),
    ]

    assert all(update["evidence_refs"] == [
        "mysql://platform/aggregate",
    ] for update in updates)
    assert all(agent.contexts[0].admin_id == 1 for agent in agents.values())


def test_admin_reviewer_allows_casual_response_without_evidence():
    reviewer = _Agent({"approved": True, "issues": []})
    registry = _Registry({"admin_final_reviewer": reviewer})
    state = {
        **_state(),
        "intent": AdminIntentDecision(
            intent=AdminIntent.CASUAL_CHAT,
            target_agent="admin_casual_chat",
        ),
        "candidate_answer": "你好，我可以提供聚合运营和模型治理分析。",
        "evidence_refs": [],
    }

    update = admin_final_reviewer.create_node(object(), registry)(state)

    assert update["review"] == ReviewResult(approved=True)


def test_model_governance_proposal_creates_draft_without_persisting_before_review():
    tool_message = ToolMessage(
        content=json.dumps({
            "evidence_refs": ["mysql://ai_models?fields=aggregate_safe"],
        }),
        tool_call_id="call-1",
    )
    agent = _Agent({
        "answer": "建议将 deepseek 设为默认模型，等待人工审批。",
        "evidence_refs": ["mysql://ai_models?fields=aggregate_safe"],
        "limitations": [],
        "proposal": {
            "model_code": "deepseek",
            "changes": {"isDefault": True},
            "summary": "将 DeepSeek 设为默认模型",
        },
    }, [tool_message])
    update = model_governance.create_node(
        object(),
        _Registry({"model_governance": agent}),
    )({
        **_state(),
        "run_id": "run-1",
    })

    assert "approval_id" not in update
    assert update["action_draft"].action_type.value == "update_model_config"
    assert update["action_draft"].parameters == {
        "code": "deepseek",
        "changes": {"isDefault": True},
    }


def test_model_governance_proposal_rejects_secret_changes():
    from app.agent.contracts import ModelConfigProposal

    with pytest.raises(ValidationError, match="敏感"):
        ModelConfigProposal(
            model_code="deepseek",
            changes={"apiKey": "secret"},
            summary="更新密钥",
        )
