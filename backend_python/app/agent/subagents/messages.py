"""Subagent 的受控会话消息构造与结构化输出降级。"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from ..contracts import ReviewResult, SpecialistResponse

# LLM 结构化输出缺失/不合规时的降级提示（与 teacher_data 的降级语义一致）
STRUCTURED_RESPONSE_FALLBACK_LIMITATION = "专业 Agent 未返回有效的结构化结果"


def parse_specialist_response(
    result: dict,
    model_cls: type[SpecialistResponse] = SpecialistResponse,
) -> SpecialistResponse | None:
    """读取 LangChain v1 结构化输出；缺失或校验失败返回 None，由调用方优雅降级。"""
    try:
        return model_cls.model_validate(
            result["structured_response"], strict=True,
        )
    except (KeyError, TypeError, ValidationError):
        return None


def degraded_specialist_update() -> dict:
    """结构化输出不合规时的安全降级节点更新（不中断整轮运行）。

    候选回答置空后，最终审核会以「候选回答为空」拒绝，
    由图的 finalize 节点给出面向用户的安全回复。
    """
    return {
        "candidate_answer": "",
        "evidence_refs": [],
        "limitations": [STRUCTURED_RESPONSE_FALLBACK_LIMITATION],
    }


def parse_review_or_reject(result: dict) -> ReviewResult:
    """读取审核结构化输出；缺失或校验失败时安全拒绝（对齐教师端 final_reviewer）。"""
    try:
        return ReviewResult.model_validate(
            result["structured_response"], strict=True,
        )
    except (KeyError, TypeError, ValidationError):
        return ReviewResult(
            approved=False,
            issues=["审核模型未返回有效的结构化结果"],
        )


def build_specialist_messages(state: dict) -> list:
    messages = []
    page_context = (state.get("page_context") or "").strip()
    if page_context:
        messages.append(SystemMessage(
            content=f"用户当前所在页面：{page_context}（仅作提示上下文，不构成任何权限）",
        ))
    summary = (state.get("conversation_summary") or "").strip()
    if summary:
        messages.append(SystemMessage(
            content=f"以下是经过服务端隔离的当前会话摘要：\n{summary}",
        ))
    for item in state.get("recent_messages", []):
        content = str(item.get("content") or "")
        if not content:
            continue
        if item.get("role") == "assistant":
            messages.append(AIMessage(content=content))
        elif item.get("role") == "user":
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=state["user_message"]))
    if state.get("revision_count", 0) > 0:
        review = state.get("review")
        issues = getattr(review, "issues", []) if review is not None else []
        candidate = str(state.get("candidate_answer") or "")
        messages.append(HumanMessage(content=(
            "请根据最终审核结果修订上一版回答。"
            "不要重复未修正的原回答，也不要扩大任务范围。\n"
            f"上一版回答：\n{candidate[:4000]}\n"
            "审核问题：\n"
            + "\n".join(f"- {issue}" for issue in issues)
        )))
    return messages


def collect_invoke_usage(result) -> dict:
    """从一次 agent.invoke 结果求和带 usage_metadata 的 AI 消息用量。

    键名对齐 contracts.UsageSummary；无用量信息返回空 dict
    （落库方按空 dict 跳过，不写零值噪音）。
    """
    if not isinstance(result, dict):
        return {}
    prompt = completion = total = 0
    seen = False
    for message in result.get("messages", []):
        usage = getattr(message, "usage_metadata", None)
        if not usage:
            continue
        seen = True
        prompt += int(usage.get("input_tokens", 0))
        completion += int(usage.get("output_tokens", 0))
        total += int(usage.get(
            "total_tokens",
            usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        ))
    if not seen:
        return {}
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def merge_usage(left: dict | None, right: dict | None) -> dict:
    """键级相加两份用量；供重试/多节点累加。"""
    left = left or {}
    right = right or {}
    if not left:
        return dict(right)
    if not right:
        return dict(left)
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


def _collect_evidence_refs(value, output: list[str]) -> None:
    if isinstance(value, dict):
        refs = value.get("evidence_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str) and ref and ref not in output:
                    output.append(ref)
        for nested in value.values():
            _collect_evidence_refs(nested, output)
    elif isinstance(value, list):
        for nested in value:
            _collect_evidence_refs(nested, output)
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return
        _collect_evidence_refs(parsed, output)


def verify_specialist_evidence(
    response: SpecialistResponse,
    agent_result: dict,
) -> SpecialistResponse:
    """只保留真实 ToolMessage 中由服务端工具返回的证据引用。"""
    observed: list[str] = []
    for message in agent_result.get("messages", []):
        if getattr(message, "type", None) == "tool":
            _collect_evidence_refs(message.content, observed)

    claimed = set(response.evidence_refs)
    unverified = claimed.difference(observed)
    limitations = list(response.limitations)
    if unverified:
        limitations.append("模型声明的部分证据未出现在实际工具结果中，已移除")
    return response.model_copy(update={
        "evidence_refs": observed,
        "limitations": limitations,
    })
