"""独立批改复核 Subagent 节点。

复核档位按提交是否含图动态选择：含图用 VISION_GRADER（多模态），
纯文本用 REVIEWER（规划阶段 3B.1）。失败降级逻辑与主批改一致。
"""
from __future__ import annotations

from typing import Callable

from ..graphs.grading import GRADING_REVIEW_NODE
from ..registry import AgentRegistry, agent_registry
from .grading import invoke_plain_grader, invoke_structured_grader


def _has_images(state: dict) -> bool:
    normalized = state.get("normalized_content")
    return bool(getattr(normalized, "image_refs", None))


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def grading_review_node(state: dict) -> dict:
        if state.get("structurer_enabled"):
            # 独立结构化路径：同一规则模型按 state.rule_model_code 独立出普通报告
            agent = reg.get_grading_agent(
                db,
                model_code=state["rule_model_code"],
                reviewer=True,
                structured=False,
            )
            return invoke_plain_grader(
                agent,
                state,
                reviewer=True,
                stage=GRADING_REVIEW_NODE,
            )
        specialist = (
            "grading_review_vision" if _has_images(state) else "grading_review"
        )
        agent = reg.get_specialist(specialist, db)
        return invoke_structured_grader(
            agent,
            state,
            reviewer=True,
            stage=GRADING_REVIEW_NODE,
        )

    return grading_review_node


__all__ = ["create_node"]
