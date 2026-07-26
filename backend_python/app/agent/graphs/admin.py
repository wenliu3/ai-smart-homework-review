"""管理员主管 LangGraph：聚合运营、审计和模型治理。"""
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.config import get_stream_writer

from ..contracts import (
    AdminIntent,
    AdminIntentDecision,
    ReviewResult,
    SpecialistResponse,
)
from ..runtime import RunCancelled
from ..supervisors.admin import AdminSupervisor

ADMIN_SUPERVISOR_NODE = "admin_supervisor"
ADMIN_CASUAL_NODE = "admin_casual_chat"
OPERATIONS_ANALYSIS_NODE = "operations_analysis_agent"
AUDIT_ANALYSIS_NODE = "audit_analysis_agent"
MODEL_GOVERNANCE_NODE = "model_governance_agent"
ADMIN_FINAL_REVIEWER_NODE = "admin_final_reviewer"
PERSIST_APPROVAL_NODE = "persist_action_draft"




def _accumulate_usage(left: dict, right: dict) -> dict:
    """usage 通道 reducer：多个节点各自回传用量，按键累加成运行总量。"""
    left = left or {}
    right = right or {}
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


class AdminAgentState(TypedDict, total=False):
    """管理员图状态。

    注意：LangGraph 会静默丢弃 schema 之外的输入键与节点更新键，
    编排层传入或节点返回的每个键都必须在此声明（对照 TeacherAgentState）。
    """
    user_message: str
    page_context: str
    conversation_summary: str
    recent_messages: list[dict]
    intent: AdminIntentDecision
    candidate_answer: str
    evidence_refs: list[str]
    limitations: list[str]
    specialist_response: SpecialistResponse
    review: ReviewResult
    final_answer: str
    visited_nodes: list[str]
    actor: object
    runtime_budget: object
    run_id: str
    action_draft: object
    approval_id: str
    usage: Annotated[dict, _accumulate_usage]


def build_admin_graph(subagents, checkpointer=None, is_cancelled=None):
    supervisor = AdminSupervisor(
        getattr(subagents, "route_classifier", None),
    )


    def emit(event):
        """通过 LangGraph custom stream 实时发送事件；invoke 模式下安全忽略。"""
        try:
            get_stream_writer()(event)
        except RuntimeError:
            pass

    def check_runtime(state):
        budget = state.get("runtime_budget")
        if budget is not None:
            budget.consume_node()
        if is_cancelled is not None and is_cancelled():
            raise RunCancelled("Agent 运行已取消")

    def with_visit(state, update, node):
        return {
            **update,
            "visited_nodes": [*state.get("visited_nodes", []), node],
        }

    def route(state):
        check_runtime(state)
        update = supervisor.route(state)
        emit({"type": "route.selected",
              "data": {"intent": update["intent"].intent.value}})
        return with_visit(state, update, ADMIN_SUPERVISOR_NODE)

    def casual(state):
        check_runtime(state)
        return with_visit(state, {
            "candidate_answer": (
                "你好，我可以分析聚合运营指标、脱敏运行审计和模型治理情况。"
            ),
            "evidence_refs": [],
        }, ADMIN_CASUAL_NODE)

    def invoke(name, method):
        def node(state):
            check_runtime(state)
            emit({"type": "agent.started", "data": {"agent": name}})
            update = method(state)
            emit({"type": "agent.completed", "data": {"agent": name}})
            return with_visit(state, update, name)

        return node

    def reviewer(state):
        check_runtime(state)
        emit({"type": "agent.started",
              "data": {"agent": ADMIN_FINAL_REVIEWER_NODE}})
        update = subagents.final_reviewer(state)
        emit({"type": "agent.completed",
              "data": {"agent": ADMIN_FINAL_REVIEWER_NODE}})
        return with_visit(state, update, ADMIN_FINAL_REVIEWER_NODE)

    def finalize(state):
        check_runtime(state)
        review = state.get("review")
        answer = (
            state.get("candidate_answer", "")
            if review and review.approved
            else "管理员回答未通过隐私与权限审核。"
        )
        return with_visit(state, {"final_answer": answer}, "finalize")

    def persist_approval(state):
        check_runtime(state)
        return with_visit(
            state,
            subagents.persist_approval(state),
            PERSIST_APPROVAL_NODE,
        )

    def after_review(state):
        review = state.get("review")
        if (
            review
            and review.approved
            and state.get("action_draft") is not None
        ):
            return PERSIST_APPROVAL_NODE
        return "finalize"

    graph = StateGraph(AdminAgentState)
    graph.add_node(ADMIN_SUPERVISOR_NODE, route)
    graph.add_node(ADMIN_CASUAL_NODE, casual)
    graph.add_node(
        OPERATIONS_ANALYSIS_NODE,
        invoke(OPERATIONS_ANALYSIS_NODE, subagents.operations_analysis),
    )
    graph.add_node(
        AUDIT_ANALYSIS_NODE,
        invoke(AUDIT_ANALYSIS_NODE, subagents.audit_analysis),
    )
    graph.add_node(
        MODEL_GOVERNANCE_NODE,
        invoke(MODEL_GOVERNANCE_NODE, subagents.model_governance),
    )
    graph.add_node(ADMIN_FINAL_REVIEWER_NODE, reviewer)
    graph.add_node(PERSIST_APPROVAL_NODE, persist_approval)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, ADMIN_SUPERVISOR_NODE)
    graph.add_conditional_edges(
        ADMIN_SUPERVISOR_NODE,
        lambda state: state["intent"].intent.value,
        {
            AdminIntent.CASUAL_CHAT.value: ADMIN_CASUAL_NODE,
            AdminIntent.OPERATIONS_ANALYSIS.value: OPERATIONS_ANALYSIS_NODE,
            AdminIntent.AUDIT_ANALYSIS.value: AUDIT_ANALYSIS_NODE,
            AdminIntent.MODEL_GOVERNANCE.value: MODEL_GOVERNANCE_NODE,
        },
    )
    for node in (
        ADMIN_CASUAL_NODE,
        OPERATIONS_ANALYSIS_NODE,
        AUDIT_ANALYSIS_NODE,
        MODEL_GOVERNANCE_NODE,
    ):
        graph.add_edge(node, ADMIN_FINAL_REVIEWER_NODE)
    graph.add_conditional_edges(
        ADMIN_FINAL_REVIEWER_NODE,
        after_review,
        {
            PERSIST_APPROVAL_NODE: PERSIST_APPROVAL_NODE,
            "finalize": "finalize",
        },
    )
    graph.add_edge(PERSIST_APPROVAL_NODE, "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = ["AdminAgentState", "build_admin_graph"]
