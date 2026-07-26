"""只解释确定性查重结果的 Subagent 节点。"""
from __future__ import annotations

import json
from typing import Callable

from langchain_core.messages import HumanMessage

from ..contracts import PlagiarismExplanation
from ..registry import AgentRegistry, agent_registry


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def plagiarism_node(state: dict) -> dict:
        agent = reg.get_specialist("plagiarism_analysis", db)
        prompt = (
            "下面是确定性查重引擎的只读结果。你只能解释风险并提出人工核查建议；"
            "不得重新计算或修改任何数值，不得认定抄袭、作弊或违纪。\n"
            + json.dumps(state["frozen_result"], ensure_ascii=False)
        )
        result = agent.invoke({
            "messages": [HumanMessage(content=prompt)],
        })
        explanation = PlagiarismExplanation.model_validate(
            result["structured_response"],
            strict=True,
        )
        return {"explanation": explanation}

    return plagiarism_node


__all__ = ["create_node"]
