"""结构化批改 Subagent 节点。

直接结构化路径（create_agent + response_format）把底层模型调用收口到
最多 2 次：模型不产出结构化工具调用（返回普通文本）或产出非法工具参数时，
LangChain 的 response_format 机制会在内部反复重试，recursion_limit 默认
9999 会造成无界模型调用。invoke_structured_grader 显式传 recursion_limit=2，
并把递归上限 / 结构化输出错误 / 校验错误统一转换为有限 grading_failure
降级信息——由图短路、任务层转教师人工，模型原始输出保留在 Artifact 里
供排查（规划阶段 3B.2 / 任务 4）。

invoke_with_repair 是录制回放评测（tests/evals）保留的旧修复循环入口，
生产 create_node 已迁移到 invoke_structured_grader。
"""
from __future__ import annotations

import json
from typing import Callable

from langchain.agents.structured_output import StructuredOutputError
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError

from ..contracts import GradingDraft
from ..graphs.grading import GRADING_AGENT_NODE
from ..registry import AgentRegistry, agent_registry
from ..runtime import BudgetExceeded
from ..tools.content import (
    build_grading_context,
    build_grading_message_content,
)
from .messages import collect_invoke_usage, merge_usage


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
    total_usage: dict = {}
    for _attempt in range(2):
        if budget is not None:
            # 剩余预算不足以完成一次模型调用时直接中断（规划 4.2），
            # 避免调用中途被 Celery 软超时打断丢失产出
            if budget.remaining_seconds < 5:
                raise BudgetExceeded("剩余预算不足以发起模型调用")
            budget.consume_model_call()
        result = agent.invoke({"messages": messages})
        total_usage = merge_usage(total_usage, collect_invoke_usage(result))
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
        return {
            "review_draft" if reviewer else "grading_draft": draft,
            "usage": total_usage,
        }
    return {
        "grading_failure": {
            "stage": stage,
            "error": last_error[:1000],
            "raw_response": raw_response[:4000],
        },
        "usage": total_usage,
    }


def _grading_failure(stage: str, error: str, raw_response: str) -> dict:
    """统一的有限降级信息：{stage, error, raw_response} 供 Artifact 留证。"""
    return {
        "grading_failure": {
            "stage": stage,
            "error": error[:1000],
            "raw_response": raw_response[:4000],
        },
    }


def invoke_structured_grader(
    agent,
    state: dict,
    *,
    reviewer: bool,
    stage: str,
) -> dict:
    """调用结构化批改模型并校验输出；底层模型调用锁定到最多 2 次。

    LangChain create_agent 的 response_format 机制在模型不产出结构化工具
    调用（返回普通文本）或产出非法工具参数时会在内部反复重试，默认
    recursion_limit 高达 9999，形成无界模型调用。这里显式传
    recursion_limit=2 收口，并把 GraphRecursionError / 结构化输出错误 /
    pydantic 校验错误统一转换为有限 grading_failure（stage/error/raw_response）。

    BudgetExceeded 不在降级范围内——预算耗尽必须中断而不是降级。
    """
    budget = state.get("runtime_budget")
    content = _grading_message_content(state, reviewer=reviewer)
    messages = [HumanMessage(content=content)]
    if budget is not None:
        # 剩余预算不足以完成一次模型调用时直接中断（规划 4.2），
        # 避免调用中途被 Celery 软超时打断丢失产出
        if budget.remaining_seconds < 5:
            raise BudgetExceeded("剩余预算不足以发起模型调用")
        budget.consume_model_call()
    try:
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": 2},
        )
    except (
        GraphRecursionError,
        StructuredOutputError,
        ValidationError,
    ) as exc:
        return {
            **_grading_failure(stage, str(exc), ""),
            "usage": {},
        }
    # 模型调用已返回：预算仍须有余量，否则中断而不是使用可能不完整的产出
    if budget is not None and budget.remaining_seconds < 5:
        raise BudgetExceeded("模型调用返回后剩余预算不足")
    total_usage = merge_usage({}, collect_invoke_usage(result))
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
        return {
            **_grading_failure(stage, str(exc), raw_response),
            "usage": total_usage,
        }
    return {
        "review_draft" if reviewer else "grading_draft": draft,
        "usage": total_usage,
    }


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def grading_node(state: dict) -> dict:
        agent = reg.get_specialist("grading", db)
        return invoke_structured_grader(
            agent,
            state,
            reviewer=False,
            stage=GRADING_AGENT_NODE,
        )

    return grading_node


__all__ = ["create_node", "invoke_structured_grader", "invoke_with_repair"]
