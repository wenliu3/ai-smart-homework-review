"""双 Agent 批改 LangGraph。"""
from __future__ import annotations

from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from ..contracts import GradingDraft, GradingOutcome, GradingRubric

NORMALIZE_CONTENT_NODE = "normalize_submission_content"
GRADING_AGENT_NODE = "grading_agent"
GRADING_REVIEW_NODE = "grading_review_agent"
GRADING_DECISION_NODE = "grading_decision"


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
    # 结构化校验失败（含一次修复重试后仍失败）时的降级信息：
    # {stage, error, raw_response}；存在即跳过后续节点，任务层转人工
    grading_failure: dict
    outcome: GradingOutcome
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
    review_node: Callable[[dict], dict],
    checkpointer=None,
):
    """构建规范化 → 主批改 → 独立复核 → 确定性决策工作流。

    批改/复核节点返回 grading_failure 时短路到 END——结果转教师人工，
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
        primary = state["grading_draft"].validate_against(rubric)
        review = state["review_draft"].validate_against(rubric)
        difference = abs(primary.total_score - review.total_score)
        reasons: list[str] = []
        if difference > rubric.total_score * 0.10:
            reasons.append("两次独立评分差异超过满分 10%")
        reasons.extend(_draft_review_reasons(primary, "主批改"))
        reasons.extend(_draft_review_reasons(review, "复核"))
        # 去重保序
        reasons = list(dict.fromkeys(reasons))
        outcome = GradingOutcome(
            primary=primary,
            review=review,
            score_difference=difference,
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
    graph.add_node(
        GRADING_REVIEW_NODE,
        _run(GRADING_REVIEW_NODE, review_node),
    )
    graph.add_node(GRADING_DECISION_NODE, decide)
    graph.add_edge(START, NORMALIZE_CONTENT_NODE)
    graph.add_edge(NORMALIZE_CONTENT_NODE, GRADING_AGENT_NODE)
    graph.add_conditional_edges(
        GRADING_AGENT_NODE,
        after_node,
        {"ok": GRADING_REVIEW_NODE, "failed": END},
    )
    graph.add_conditional_edges(
        GRADING_REVIEW_NODE,
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
