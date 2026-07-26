"""管理员模型治理分析 Subagent；只读分析，不直接修改配置。"""
from typing import Callable

from ..contracts import ModelGovernanceResponse
from ..tools.approval import create_action_draft
from ..registry import AgentRegistry, agent_registry
from ..tools.admin import AdminContext
from .messages import (
    build_specialist_messages,
    degraded_specialist_update,
    parse_specialist_response,
    verify_specialist_evidence,
)


def create_node(
    db,
    registry: AgentRegistry | None = None,
) -> Callable:
    reg = registry or agent_registry

    def node(state: dict) -> dict:
        agent = reg.get_specialist("model_governance", db)
        result = agent.invoke(
            {"messages": build_specialist_messages(state)},
            context=AdminContext(
                admin_id=state["actor"].user_id,
                budget=state.get("runtime_budget"),
            ),
        )
        response = parse_specialist_response(result, ModelGovernanceResponse)
        if response is None:
            return degraded_specialist_update()
        response = verify_specialist_evidence(response, result)
        update = {
            "candidate_answer": response.answer,
            "evidence_refs": response.evidence_refs,
            "limitations": response.limitations,
            "specialist_response": response,
        }
        if response.proposal is not None:
            proposal = response.proposal
            draft = create_action_draft(
                action_type="update_model_config",
                target_type="ai_model",
                target_id=proposal.model_code,
                parameters={
                    "code": proposal.model_code,
                    "changes": proposal.changes,
                },
                summary=proposal.summary,
                risk_level="high",
                idempotency_seed=state.get("run_id", ""),
            )
            update["action_draft"] = draft
        return update

    return node


__all__ = ["create_node"]
