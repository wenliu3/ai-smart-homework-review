"""查重解释的最终审核 Subagent 节点（架构手册 §6 Explain→Review→Output）。"""
from __future__ import annotations

import json
from typing import Callable

from langchain_core.messages import HumanMessage

from ..registry import AgentRegistry, agent_registry
from .messages import parse_review_or_reject


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def plagiarism_review_node(state: dict) -> dict:
        agent = reg.get_specialist("plagiarism_review", db)
        prompt = (
            "审核下面这段查重解释是否安全合规。\n"
            "拒绝条件：认定抄袭/作弊/违纪、编造或修改查重数值、"
            "泄露学生敏感信息、超出解释与人工核查建议的范围。\n"
            "引擎只读结果：\n"
            + json.dumps(state["frozen_result"], ensure_ascii=False)
            + "\n候选解释：\n"
            + state["explanation"].explanation
            + "\n人工核查建议：\n"
            + json.dumps(
                state["explanation"].review_suggestions, ensure_ascii=False,
            )
        )
        result = agent.invoke({
            "messages": [HumanMessage(content=prompt)],
        })
        return {"review": parse_review_or_reject(result)}

    return plagiarism_review_node


__all__ = ["create_node"]
