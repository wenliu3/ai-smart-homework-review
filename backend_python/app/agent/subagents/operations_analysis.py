"""管理员平台运营聚合分析 Subagent。"""
from typing import Callable

from ..registry import AgentRegistry, agent_registry
from ..tools.admin import AdminContext
from .messages import (
    build_specialist_messages,
    degraded_specialist_update,
    parse_specialist_response,
    verify_specialist_evidence,
)


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def node(state: dict) -> dict:
        agent = reg.get_specialist("operations_analysis", db)
        result = agent.invoke(
            {"messages": build_specialist_messages(state)},
            context=AdminContext(
                admin_id=state["actor"].user_id,
                budget=state.get("runtime_budget"),
            ),
        )
        response = parse_specialist_response(result)
        if response is None:
            return degraded_specialist_update()
        response = verify_specialist_evidence(response, result)
        return {
            "candidate_answer": response.answer,
            "evidence_refs": response.evidence_refs,
            "limitations": response.limitations,
            "specialist_response": response,
        }

    return node


__all__ = ["create_node"]
