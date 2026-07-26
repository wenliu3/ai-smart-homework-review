"""ActionDraft 人工审批协调 Graph。

首次调用只校验并持久化 pending 草案；前端完成授权后，以 approval_id 和
decision 再次调用进入执行或拒绝节点。持久化与恢复边界由审批 API 管理。
"""
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from ..contracts import ActionDraft

VALIDATE_ACTION_DRAFT_NODE = "validate_action_draft"
PERSIST_PENDING_APPROVAL_NODE = "persist_pending_approval"
EXECUTE_APPROVED_ACTION_NODE = "execute_approved_action"
REJECT_ACTION_NODE = "reject_action"


class ApprovalState(TypedDict, total=False):
    draft: ActionDraft
    approval_id: str
    decision: Literal["approved", "rejected"]
    status: str
    result: dict


def build_approval_graph(coordinator, checkpointer=None):
    graph = StateGraph(ApprovalState)
    graph.add_node(VALIDATE_ACTION_DRAFT_NODE, coordinator.validate)
    graph.add_node(PERSIST_PENDING_APPROVAL_NODE, coordinator.persist)
    graph.add_node(EXECUTE_APPROVED_ACTION_NODE, coordinator.execute)
    graph.add_node(REJECT_ACTION_NODE, coordinator.reject)

    def enter(state: ApprovalState):
        if not state.get("approval_id"):
            return "draft"
        return state.get("decision", "rejected")

    graph.add_conditional_edges(
        START,
        enter,
        {
            "draft": VALIDATE_ACTION_DRAFT_NODE,
            "approved": EXECUTE_APPROVED_ACTION_NODE,
            "rejected": REJECT_ACTION_NODE,
        },
    )
    graph.add_edge(VALIDATE_ACTION_DRAFT_NODE, PERSIST_PENDING_APPROVAL_NODE)
    graph.add_edge(PERSIST_PENDING_APPROVAL_NODE, END)
    graph.add_edge(EXECUTE_APPROVED_ACTION_NODE, END)
    graph.add_edge(REJECT_ACTION_NODE, END)
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "ApprovalState",
    "EXECUTE_APPROVED_ACTION_NODE",
    "PERSIST_PENDING_APPROVAL_NODE",
    "REJECT_ACTION_NODE",
    "VALIDATE_ACTION_DRAFT_NODE",
    "build_approval_graph",
]
