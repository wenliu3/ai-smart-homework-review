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
    grading_draft: GradingDraft
    review_draft: GradingDraft
    outcome: GradingOutcome
    visited_nodes: list[str]


def build_grading_graph(
    normalize_node: Callable[[dict], dict],
    grading_node: Callable[[dict], dict],
    review_node: Callable[[dict], dict],
    checkpointer=None,
):
    """构建规范化 → 主批改 → 独立复核 → 确定性决策工作流。"""

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
        outcome = GradingOutcome(
            primary=primary,
            review=review,
            score_difference=difference,
            needs_human_review=difference > rubric.total_score * 0.10,
        )
        return {
            "outcome": outcome,
            "visited_nodes": [
                *state.get("visited_nodes", []),
                GRADING_DECISION_NODE,
            ],
        }

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
    graph.add_edge(GRADING_AGENT_NODE, GRADING_REVIEW_NODE)
    graph.add_edge(GRADING_REVIEW_NODE, GRADING_DECISION_NODE)
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
