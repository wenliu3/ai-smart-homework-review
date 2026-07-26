"""独立批改复核 Subagent 节点。"""
from __future__ import annotations

from typing import Callable

from langchain_core.messages import HumanMessage

from ..contracts import GradingDraft
from ..registry import AgentRegistry, agent_registry
from .grading import _grading_message_content


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def grading_review_node(state: dict) -> dict:
        agent = reg.get_specialist("grading_review", db)
        result = agent.invoke({
            "messages": [HumanMessage(content=_grading_message_content(
                state,
                reviewer=True,
            ))],
        })
        draft = GradingDraft.model_validate(
            result["structured_response"],
            strict=True,
        ).validate_against(state["rubric"])
        return {"review_draft": draft}

    return grading_review_node


__all__ = ["create_node"]
