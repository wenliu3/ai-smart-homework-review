"""结构化批改 Subagent 节点。"""
from __future__ import annotations

import json
from typing import Callable

from langchain_core.messages import HumanMessage

from ..contracts import GradingDraft
from ..registry import AgentRegistry, agent_registry
from ..tools.content import build_grading_input, build_grading_message_content


def _grading_prompt(state: dict, *, reviewer: bool) -> str:
    rubric = state["rubric"]
    normalized = state["normalized_content"]
    role = "独立复核" if reviewer else "首次批改"
    return (
        f"执行{role}。必须逐项使用评分量表，不得从自然语言解析或生成可信总分。\n"
        "评分量表：\n"
        f"{json.dumps(rubric.model_dump(), ensure_ascii=False)}\n\n"
        f"{build_grading_input(normalized)}"
    )


def _grading_message_content(state: dict, *, reviewer: bool) -> list[dict]:
    image_blocks = build_grading_message_content(
        state["normalized_content"],
    )[1:]
    return [
        {"type": "text", "text": _grading_prompt(state, reviewer=reviewer)},
        *image_blocks,
    ]


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def grading_node(state: dict) -> dict:
        agent = reg.get_specialist("grading", db)
        result = agent.invoke({
            "messages": [HumanMessage(content=_grading_message_content(
                state,
                reviewer=False,
            ))],
        })
        draft = GradingDraft.model_validate(
            result["structured_response"],
            strict=True,
        ).validate_against(state["rubric"])
        return {"grading_draft": draft}

    return grading_node


__all__ = ["create_node"]
