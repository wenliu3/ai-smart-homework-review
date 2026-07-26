"""结构化批改 Subagent 节点。

校验失败先做一次格式修复重试（把校验错误回喂模型）；仍失败时返回
grading_failure 降级信息而不是抛异常——由图短路、任务层转教师人工，
模型原始输出保留在 Artifact 里供排查（规划阶段 3B.2）。
"""
from __future__ import annotations

import json
from typing import Callable

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from ..contracts import GradingDraft
from ..graphs.grading import GRADING_AGENT_NODE
from ..registry import AgentRegistry, agent_registry
from ..tools.content import (
    build_grading_context,
    build_grading_message_content,
)


def _grading_prompt(state: dict, *, reviewer: bool) -> str:
    rubric = state["rubric"]
    role = "独立复核" if reviewer else "首次批改"
    return (
        f"执行{role}。必须逐项使用评分量表，不得从自然语言解析或生成可信总分。\n"
        "评分量表：\n"
        f"{json.dumps(rubric.model_dump(), ensure_ascii=False)}\n"
        + build_grading_context(
            state["normalized_content"],
            assignment_description=state.get("assignment_description", ""),
            reference_materials=state.get("reference_materials", ""),
        )
    )


def _grading_message_content(state: dict, *, reviewer: bool) -> list[dict]:
    image_blocks = build_grading_message_content(
        state["normalized_content"],
    )[1:]
    return [
        {"type": "text", "text": _grading_prompt(state, reviewer=reviewer)},
        *image_blocks,
    ]


def invoke_with_repair(
    agent,
    state: dict,
    *,
    reviewer: bool,
    stage: str,
) -> dict:
    """调用批改模型并校验结构化输出；失败重试一次，仍失败返回降级信息。

    BudgetExceeded 不在捕获范围内——预算耗尽必须中断而不是降级。
    """
    budget = state.get("runtime_budget")
    content = _grading_message_content(state, reviewer=reviewer)
    messages = [HumanMessage(content=content)]
    last_error = ""
    raw_response = ""
    for _attempt in range(2):
        if budget is not None:
            budget.consume_model_call()
        result = agent.invoke({"messages": messages})
        raw = result.get("structured_response") if isinstance(result, dict) else None
        raw_response = (
            json.dumps(raw, ensure_ascii=False, default=str)
            if raw is not None
            else ""
        )
        try:
            draft = GradingDraft.model_validate(
                raw, strict=True,
            ).validate_against(state["rubric"])
        except (ValidationError, TypeError, ValueError) as exc:
            last_error = str(exc)
            # 第一次失败：错误与原输出一起回喂，让模型定向修复格式
            messages = [
                HumanMessage(content=content),
                HumanMessage(content=(
                    "上一次输出未通过结构化校验，请修复后重新输出完整的逐项评分。\n"
                    f"校验错误：{last_error[:1000]}\n"
                    f"上一次输出：{raw_response[:2000]}"
                )),
            ]
            continue
        return {"review_draft" if reviewer else "grading_draft": draft}
    return {"grading_failure": {
        "stage": stage,
        "error": last_error[:1000],
        "raw_response": raw_response[:4000],
    }}


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def grading_node(state: dict) -> dict:
        agent = reg.get_specialist("grading", db)
        return invoke_with_repair(
            agent,
            state,
            reviewer=False,
            stage=GRADING_AGENT_NODE,
        )

    return grading_node


__all__ = ["create_node", "invoke_with_repair"]
