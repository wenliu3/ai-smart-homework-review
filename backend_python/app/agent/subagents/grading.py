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
import re
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

# 匹配 ```json ... ``` 代码块
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_structured_payload(text: str) -> dict | None:
    """从模型输出文本中正则提取 JSON 载荷。

    模型按提示词以固定 JSON 格式输出，但可能包裹代码块或附带说明。
    依次尝试：代码块 → 首 { 到末 } 的片段 → 直接 json.loads。
    """
    if not text:
        return None
    candidates: list[str] = []
    block = _JSON_BLOCK_RE.search(text)
    if block:
        candidates.append(block.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start:end + 1])
    candidates.append(text.strip())
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except (json.JSONDecodeError, ValueError):
            continue
    return None

# 直接结构化路径的预算余量守卫（秒）：进入 Agent 前/返回后都要求剩余不少于此值
MIN_GRADING_BUDGET_SECONDS = 5
# 直接结构化路径的底层模型调用上限：recursion_limit 收口值，也是测试断言基准。
# 2 对"模型一次成功产出"够用，但 AI 在复杂作业上常需先尝试工具调用再重试，
# 2 步会过早截断导致整次批改降级转人工。提到 5 给足重试空间，同时仍限制无限自循环。
MAX_STRUCTURED_CALLS = 5


def _consume_model_call(budget) -> None:
    """进入 Agent 前守卫并消费一次模型调用预算。

    剩余预算不足一次调用时直接中断（规划 4.2），避免调用中途被
    Celery 软超时打断丢失产出。budget 为 None（无预算场景）时不守卫。
    """
    if budget is not None:
        if budget.remaining_seconds < MIN_GRADING_BUDGET_SECONDS:
            raise BudgetExceeded("剩余预算不足以发起模型调用")
        budget.consume_model_call()


def _assert_remaining_budget(budget, reason: str) -> None:
    """模型调用返回后校验预算仍有余量；不足则中断而不是降级。"""
    if budget is not None and budget.remaining_seconds < MIN_GRADING_BUDGET_SECONDS:
        raise BudgetExceeded(reason)


def _grading_prompt(state: dict, *, reviewer: bool) -> str:
    rubric = state["rubric"]
    role = "独立复核" if reviewer else "首次批改"
    dimension_count = len(rubric.criteria)
    return (
        f"执行{role}。以下评分量表共有 {dimension_count} 个评分维度，"
        f"必须且只能按这 {dimension_count} 个维度逐项评分：\n"
        "评分量表：\n"
        f"{json.dumps(rubric.model_dump(), ensure_ascii=False)}\n"
        "评分规则：\n"
        "1. 输出必须恰好包含量表中列出的每一个维度，且每个维度的 criterion_id 严格使用量表里的 id。\n"
        "2. 禁止自创、拆分、合并或新增任何维度（例如不得按作业的小题、任务或章节自拆成多个维度）。\n"
        "3. 每个维度给出 score、max_score、feedback（含得分依据与扣分原因）和 evidence_refs。\n"
        "4. 不得从自然语言解析或生成可信总分；总分由后端汇总。\n"
        "5. 严格以如下 JSON 格式输出，只输出该 JSON，不要输出任何其他文字：\n"
        '{"rubric_version": "<评分量表的version字段>",\n'
        ' "items": [{"criterion_id": "<量表里的id>", "title": "<维度名>", "score": <数字>,\n'
        '  "max_score": <数字>, "feedback": "<得分依据与扣分原因>", "evidence_refs": ["<提交证据引用>"]}],\n'
        ' "summary": "<整体总结>", "confidence": <0到1的数字或null>}\n'
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
    calls = 0
    for _attempt in range(2):
        calls += 1
        _consume_model_call(budget)
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
            **_model_usage_entry(
                state.get("rule_model_code"),
                total_usage,
                calls=calls,
            ),
        }
    return {
        "grading_failure": {
            "stage": stage,
            "error": last_error[:1000],
            "raw_response": raw_response[:4000],
        },
        "usage": total_usage,
        **_model_usage_entry(
            state.get("rule_model_code"),
            total_usage,
            calls=calls,
        ),
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


def _model_usage_entry(
    code: str | None,
    usage: dict | None,
    *,
    calls: int = 1,
) -> dict:
    """把一个节点的一次/多次模型调用归入对应 model code（model_usage 聚合）。

    code 缺失（旧单元测试未带 rule_model_code）时返回空
    字典，不产生用量条目也不抛异常。total_tokens 取本节点用量聚合的总量。
    """
    if not code:
        return {}
    tokens = int((usage or {}).get("total_tokens", 0))
    return {
        "model_usage": {
            code: {
                "calls": max(calls, 0),
                "total_tokens": tokens,
            },
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
    _consume_model_call(budget)
    try:
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": MAX_STRUCTURED_CALLS},
        )
    except (
        GraphRecursionError,
        StructuredOutputError,
        ValidationError,
    ) as exc:
        return {
            **_grading_failure(stage, str(exc), ""),
            "usage": {},
            **_model_usage_entry(state.get("rule_model_code"), {}),
        }
    # 模型调用已返回：预算仍须有余量，否则中断而不是使用可能不完整的产出
    _assert_remaining_budget(budget, "模型调用返回后剩余预算不足")
    total_usage = merge_usage({}, collect_invoke_usage(result))
    # 提取结构化载荷：优先 create_agent 的 tool_choice 产物（structured_response）；
    # 模型按提示词直接输出 JSON 文本时，从最后一条 AIMessage 正则提取。
    # （mimo 等模型对 tool_choice 强制结构化不稳定，提示词 + 正则提取更可靠）
    raw = None
    if isinstance(result, dict):
        raw = result.get("structured_response")
        if raw is None:
            for message in reversed(result.get("messages", [])):
                value = getattr(message, "content", None)
                if isinstance(value, str) and value.strip():
                    raw = _extract_structured_payload(value)
                    break
    raw_response = (
        json.dumps(raw, ensure_ascii=False, default=str)
        if raw is not None
        else ""
    )
    # rubric_version 由后端决定（量表版本），模型不应编造：一律覆盖为量表真实版本，
    # 防止模型漏输出或输出错误版本导致校验失败。
    if isinstance(raw, dict):
        raw["rubric_version"] = state["rubric"].version
    try:
        draft = GradingDraft.model_validate(
            raw, strict=True,
        ).validate_against(state["rubric"])
    except (ValidationError, TypeError, ValueError) as exc:
        return {
            **_grading_failure(stage, str(exc), raw_response),
            "usage": total_usage,
            **_model_usage_entry(state.get("rule_model_code"), total_usage),
        }
    return {
        "review_draft" if reviewer else "grading_draft": draft,
        "usage": total_usage,
        **_model_usage_entry(state.get("rule_model_code"), total_usage),
    }


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def grading_node(state: dict) -> dict:
        # 单 Agent：用 AI 规则指定的模型，按提示词输出固定 JSON，由 invoke 侧正则提取。
        # 不依赖 tool_choice 强制结构化（mimo 等模型对强制 tool_choice 不稳定，
        # 大输入下常返回空导致整次降级），提示词 + 正则提取更可靠。
        model_code = state.get("rule_model_code")
        if model_code:
            agent = reg.get_grading_agent(
                db,
                model_code=model_code,
                reviewer=False,
                structured=False,
            )
        else:
            # 兼容无路由的单元测试：默认批改 agent（tool_choice 产物同样能被提取）
            agent = reg.get_specialist("grading", db)
        return invoke_structured_grader(
            agent,
            state,
            reviewer=False,
            stage=GRADING_AGENT_NODE,
        )

    return grading_node


__all__ = [
    "create_node",
    "invoke_structured_grader",
    "invoke_with_repair",
]
