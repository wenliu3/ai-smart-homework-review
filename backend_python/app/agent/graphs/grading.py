"""单 Agent 批改 LangGraph。"""
from __future__ import annotations

from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from ..contracts import GradingDraft, GradingOutcome, GradingRubric

NORMALIZE_CONTENT_NODE = "normalize_submission_content"
GRADING_AGENT_NODE = "grading_agent"
GRADING_REVIEW_NODE = "grading_review_agent"
GRADING_DECISION_NODE = "grading_decision"




def _accumulate_usage(left: dict, right: dict) -> dict:
    """usage 通道 reducer：多个节点各自回传用量，按键累加成运行总量。"""
    left = left or {}
    right = right or {}
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


def _accumulate_model_usage(left: dict, right: dict) -> dict:
    """model_usage 通道 reducer：按 model_code 累加 calls 与 total_tokens。

    每个节点把 {code: {"calls": N, "total_tokens": T}} 归入对应模型 code，
    这里把同一 code 的多节点贡献合并成运行级单模型用量。
    """
    left = left or {}
    right = right or {}
    result: dict = {}
    for code in {*left, *right}:
        l = left.get(code) or {}
        r = right.get(code) or {}
        result[code] = {
            "calls": int(l.get("calls", 0)) + int(r.get("calls", 0)),
            "total_tokens": int(l.get("total_tokens", 0)) + int(r.get("total_tokens", 0)),
        }
    return result


class GradingState(TypedDict, total=False):
    submission_id: int
    submission_count: int
    rubric: GradingRubric
    normalized_content: object
    # 作业要求与教师参考资料（3B.1）：由任务层从 Assignment 读出后传入
    assignment_description: str
    reference_materials: str
    runtime_budget: object
    grading_draft: GradingDraft
    review_draft: GradingDraft
    # 单 Agent 路由：规则模型 code 与规则文本（来自作业快照 ai_rule.modelType）
    rule_prompt: str
    rule_model_code: str
    # 结构化校验失败（含一次修复重试后仍失败）时的降级信息：
    # {stage, error, raw_response}；存在即跳过后续节点，任务层转人工
    grading_failure: dict
    outcome: GradingOutcome
    usage: Annotated[dict, _accumulate_usage]
    # 按实际模型 code 拆分的运行级用量：{code: {"calls": N, "total_tokens": T}}
    model_usage: Annotated[dict, _accumulate_model_usage]
    visited_nodes: list[str]


def _draft_review_reasons(draft: GradingDraft, role: str) -> list[str]:
    """单份草案的确定性转人工检查：证据缺失 + 模型自报。"""
    reasons: list[str] = []
    missing = [
        item.criterion_id for item in draft.items if not item.evidence_refs
    ]
    if missing:
        reasons.append(
            f"{role}评分缺少提交证据：{'、'.join(missing)}",
        )
    if draft.requires_human_review:
        reasons.extend(draft.review_reasons)
    return reasons


def build_grading_graph(
    normalize_node: Callable[[dict], dict],
    grading_node: Callable[[dict], dict],
    checkpointer=None,
):
    """构建单 Agent 批改图：规范化 → 主批改 → 确定性决策。

    主批改节点返回 grading_failure 时短路到 END——结果转教师人工，
    而不是让异常把整个 run 打成 failed 并丢弃模型产出。
    """

    def _run(node_name: str, node: Callable[[dict], dict]):
        def wrapped(state: GradingState) -> dict:
            update = dict(node(state))
            update["visited_nodes"] = [
                *state.get("visited_nodes", []),
                node_name,
            ]
            return update

        return wrapped

    def decide(state: GradingState) -> dict:
        rubric = state["rubric"]
        # 单 Agent 模式：主批改草案即最终结果，不做双评分比较。
        # 仍做确定性的转人工检查（证据缺失 / 模型自报需人工）。
        draft = state["grading_draft"].validate_against(rubric)
        reasons = _draft_review_reasons(draft, "主批改")
        outcome = GradingOutcome(
            primary=draft,
            review=draft,
            score_difference=0,
            needs_human_review=bool(reasons),
            review_reasons=reasons,
        )
        return {
            "outcome": outcome,
            "visited_nodes": [
                *state.get("visited_nodes", []),
                GRADING_DECISION_NODE,
            ],
        }

    def after_node(state: GradingState) -> str:
        return "failed" if state.get("grading_failure") else "ok"

    graph = StateGraph(GradingState)
    graph.add_node(
        NORMALIZE_CONTENT_NODE,
        _run(NORMALIZE_CONTENT_NODE, normalize_node),
    )
    graph.add_node(
        GRADING_AGENT_NODE,
        _run(GRADING_AGENT_NODE, grading_node),
    )
    graph.add_node(GRADING_DECISION_NODE, decide)
    graph.add_edge(START, NORMALIZE_CONTENT_NODE)
    graph.add_edge(NORMALIZE_CONTENT_NODE, GRADING_AGENT_NODE)
    graph.add_conditional_edges(
        GRADING_AGENT_NODE,
        after_node,
        {"ok": GRADING_DECISION_NODE, "failed": END},
    )
    graph.add_edge(GRADING_DECISION_NODE, END)
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "GRADING_AGENT_NODE",
    "GRADING_DECISION_NODE",
    "GRADING_REVIEW_NODE",
    "GradingState",
    "NORMALIZE_CONTENT_NODE",
    "build_grading_graph",
]
