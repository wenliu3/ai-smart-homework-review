"""确定性查重结果解释 LangGraph。"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from ..contracts import PlagiarismAnalysis, PlagiarismExplanation

FREEZE_RESULT_NODE = "freeze_plagiarism_result"
PLAGIARISM_ANALYSIS_NODE = "plagiarism_analysis_agent"
FINALIZE_PLAGIARISM_NODE = "finalize_plagiarism_analysis"


class PlagiarismState(TypedDict, total=False):
    deterministic_result: dict
    frozen_result: dict
    explanation: PlagiarismExplanation
    analysis: PlagiarismAnalysis
    visited_nodes: list[str]


def build_plagiarism_graph(
    explanation_node: Callable[[dict], dict],
    checkpointer=None,
):
    """模型只处理解释字段；引擎数值和证据在服务端深拷贝冻结。"""

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

    def finalize(state: PlagiarismState) -> dict:
        return {
            "analysis": PlagiarismAnalysis(
                deterministic_result=deepcopy(state["frozen_result"]),
                explanation=state["explanation"],
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
    graph.add_edge(PLAGIARISM_ANALYSIS_NODE, FINALIZE_PLAGIARISM_NODE)
    graph.add_edge(FINALIZE_PLAGIARISM_NODE, END)
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "FINALIZE_PLAGIARISM_NODE",
    "FREEZE_RESULT_NODE",
    "PLAGIARISM_ANALYSIS_NODE",
    "PlagiarismState",
    "build_plagiarism_graph",
]
