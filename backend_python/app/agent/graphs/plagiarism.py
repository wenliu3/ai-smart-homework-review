"""确定性查重结果解释 LangGraph（Explain → Review → Output，架构手册 §6）。"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from ..contracts import PlagiarismAnalysis, PlagiarismExplanation, ReviewResult

FREEZE_RESULT_NODE = "freeze_plagiarism_result"
PLAGIARISM_ANALYSIS_NODE = "plagiarism_analysis_agent"
PLAGIARISM_REVIEW_NODE = "plagiarism_review_agent"
FINALIZE_PLAGIARISM_NODE = "finalize_plagiarism_analysis"

# 审核拒绝时的安全兜底解释：不透出被拒的模型文本
SAFE_EXPLANATION_FALLBACK = (
    "AI 解释未通过安全审核。请教师根据查重数值自行判断，"
    "并人工核查命中片段与引用格式。"
)




def _accumulate_usage(left: dict, right: dict) -> dict:
    """usage 通道 reducer：多个节点各自回传用量，按键累加成运行总量。"""
    left = left or {}
    right = right or {}
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


class PlagiarismState(TypedDict, total=False):
    deterministic_result: dict
    # 学生作业内容节选（截断后），供解释节点引用具体文本；不可信
    submission_excerpt: str
    frozen_result: dict
    explanation: PlagiarismExplanation
    review: ReviewResult
    analysis: PlagiarismAnalysis
    usage: Annotated[dict, _accumulate_usage]
    visited_nodes: list[str]


def build_plagiarism_graph(
    explanation_node: Callable[[dict], dict],
    review_node: Callable[[dict], dict] | None = None,
    checkpointer=None,
):
    """模型只处理解释字段；引擎数值和证据在服务端深拷贝冻结。

    review_node 为 None 时保持旧拓扑（Explain→Output），供既有调用方
    渐进迁移；生产路径必须传入审核节点。
    """

    def freeze(state: PlagiarismState) -> dict:
        return {
            "frozen_result": deepcopy(state["deterministic_result"]),
            "visited_nodes": [
                *state.get("visited_nodes", []),
                FREEZE_RESULT_NODE,
            ],
        }

    def explain(state: PlagiarismState) -> dict:
        update = dict(explanation_node(state))
        update["explanation"] = PlagiarismExplanation.model_validate(
            update["explanation"],
            strict=True,
        )
        update["visited_nodes"] = [
            *state.get("visited_nodes", []),
            PLAGIARISM_ANALYSIS_NODE,
        ]
        return update

    def review(state: PlagiarismState) -> dict:
        update = dict(review_node(state))
        update["visited_nodes"] = [
            *state.get("visited_nodes", []),
            PLAGIARISM_REVIEW_NODE,
        ]
        return update

    def finalize(state: PlagiarismState) -> dict:
        explanation = state["explanation"]
        verdict = state.get("review")
        if verdict is not None and not verdict.approved:
            # 拒绝即整体降级为兜底文案，不做逐段挑拣（决策 D5 同源原则）
            explanation = PlagiarismExplanation(
                explanation=SAFE_EXPLANATION_FALLBACK,
                review_suggestions=[],
            )
        return {
            "analysis": PlagiarismAnalysis(
                deterministic_result=deepcopy(state["frozen_result"]),
                explanation=explanation,
            ),
            "visited_nodes": [
                *state.get("visited_nodes", []),
                FINALIZE_PLAGIARISM_NODE,
            ],
        }

    graph = StateGraph(PlagiarismState)
    graph.add_node(FREEZE_RESULT_NODE, freeze)
    graph.add_node(PLAGIARISM_ANALYSIS_NODE, explain)
    graph.add_node(FINALIZE_PLAGIARISM_NODE, finalize)
    graph.add_edge(START, FREEZE_RESULT_NODE)
    graph.add_edge(FREEZE_RESULT_NODE, PLAGIARISM_ANALYSIS_NODE)
    if review_node is not None:
        graph.add_node(PLAGIARISM_REVIEW_NODE, review)
        graph.add_edge(PLAGIARISM_ANALYSIS_NODE, PLAGIARISM_REVIEW_NODE)
        graph.add_edge(PLAGIARISM_REVIEW_NODE, FINALIZE_PLAGIARISM_NODE)
    else:
        graph.add_edge(PLAGIARISM_ANALYSIS_NODE, FINALIZE_PLAGIARISM_NODE)
    graph.add_edge(FINALIZE_PLAGIARISM_NODE, END)
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "FINALIZE_PLAGIARISM_NODE",
    "FREEZE_RESULT_NODE",
    "PLAGIARISM_ANALYSIS_NODE",
    "PLAGIARISM_REVIEW_NODE",
    "PlagiarismState",
    "SAFE_EXPLANATION_FALLBACK",
    "build_plagiarism_graph",
]
