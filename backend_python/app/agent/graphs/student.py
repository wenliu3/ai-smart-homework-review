"""学生主管 LangGraph：辅导、反馈解释、学习规划与防代写。"""
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from ..contracts import (
    ReviewResult,
    SpecialistResponse,
    StudentIntent,
    StudentIntentDecision,
)
from ..runtime import RunCancelled
from ..supervisors.student import StudentSupervisor

STUDENT_SUPERVISOR_NODE = "student_supervisor"
STUDENT_CASUAL_NODE = "student_casual_chat"
LEARNING_COACH_NODE = "learning_coach_agent"
FEEDBACK_EXPLAINER_NODE = "feedback_explainer_agent"
LEARNING_PLANNER_NODE = "learning_planner_agent"
PROHIBITED_ANSWER_NODE = "prohibited_answer"
STUDENT_FINAL_REVIEWER_NODE = "student_final_reviewer"

_PROHIBITED_RESPONSE = (
    "我不能代写或提供可直接提交的完整答案。"
    "我可以通过拆解题目、提示关键概念、检查你的思路来帮助你自己完成。"
)
_SAFE_REJECTION = "这次回答没有通过学生安全审核，我可以换成提示和步骤引导。"




def _accumulate_usage(left: dict, right: dict) -> dict:
    """usage 通道 reducer：多个节点各自回传用量，按键累加成运行总量。"""
    left = left or {}
    right = right or {}
    return {
        key: left.get(key, 0) + right.get(key, 0)
        for key in {*left, *right}
    }


class StudentAgentState(TypedDict, total=False):
    """学生图状态。

    注意：LangGraph 会静默丢弃 schema 之外的输入键与节点更新键，
    编排层传入或节点返回的每个键都必须在此声明（对照 TeacherAgentState）。
    """
    run_id: str
    user_message: str
    conversation_summary: str
    recent_messages: list[dict]
    intent: StudentIntentDecision
    candidate_answer: str
    evidence_refs: list[str]
    limitations: list[str]
    specialist_response: SpecialistResponse
    review: ReviewResult
    final_answer: str
    visited_nodes: list[str]
    actor: object
    runtime_budget: object


def build_student_graph(subagents, checkpointer=None, is_cancelled=None):
    supervisor = StudentSupervisor()

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
        return with_visit(
            state,
            supervisor.route(state),
            STUDENT_SUPERVISOR_NODE,
        )

    def casual(state):
        check_runtime(state)
        return with_visit(state, {
            "candidate_answer": (
                "你好，我是学习助手。我可以提供思路提示、解释反馈并帮助制定学习计划。"
            ),
            "evidence_refs": [],
        }, STUDENT_CASUAL_NODE)

    def prohibited(state):
        check_runtime(state)
        return with_visit(state, {
            "candidate_answer": _PROHIBITED_RESPONSE,
            "evidence_refs": [],
        }, PROHIBITED_ANSWER_NODE)

    def invoke(name, method):
        def node(state):
            check_runtime(state)
            return with_visit(state, method(state), name)

        return node

    def reviewer(state):
        check_runtime(state)
        return with_visit(
            state,
            subagents.final_reviewer(state),
            STUDENT_FINAL_REVIEWER_NODE,
        )

    def finalize(state):
        check_runtime(state)
        review = state.get("review")
        answer = (
            state.get("candidate_answer", "")
            if review and review.approved
            else _SAFE_REJECTION
        )
        return with_visit(state, {"final_answer": answer}, "finalize")

    def select(state):
        return state["intent"].intent.value

    graph = StateGraph(StudentAgentState)
    graph.add_node(STUDENT_SUPERVISOR_NODE, route)
    graph.add_node(STUDENT_CASUAL_NODE, casual)
    graph.add_node(
        LEARNING_COACH_NODE,
        invoke(LEARNING_COACH_NODE, subagents.learning_coach),
    )
    graph.add_node(
        FEEDBACK_EXPLAINER_NODE,
        invoke(FEEDBACK_EXPLAINER_NODE, subagents.feedback_explainer),
    )
    graph.add_node(
        LEARNING_PLANNER_NODE,
        invoke(LEARNING_PLANNER_NODE, subagents.learning_planner),
    )
    graph.add_node(PROHIBITED_ANSWER_NODE, prohibited)
    graph.add_node(STUDENT_FINAL_REVIEWER_NODE, reviewer)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, STUDENT_SUPERVISOR_NODE)
    graph.add_conditional_edges(
        STUDENT_SUPERVISOR_NODE,
        select,
        {
            StudentIntent.CASUAL_CHAT.value: STUDENT_CASUAL_NODE,
            StudentIntent.LEARNING_COACH.value: LEARNING_COACH_NODE,
            StudentIntent.FEEDBACK_EXPLANATION.value: FEEDBACK_EXPLAINER_NODE,
            StudentIntent.LEARNING_PLAN.value: LEARNING_PLANNER_NODE,
            StudentIntent.PROHIBITED_ANSWER.value: PROHIBITED_ANSWER_NODE,
        },
    )
    for node in (
        STUDENT_CASUAL_NODE,
        LEARNING_COACH_NODE,
        FEEDBACK_EXPLAINER_NODE,
        LEARNING_PLANNER_NODE,
        PROHIBITED_ANSWER_NODE,
    ):
        graph.add_edge(node, STUDENT_FINAL_REVIEWER_NODE)
    graph.add_edge(STUDENT_FINAL_REVIEWER_NODE, "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


__all__ = [
    "StudentAgentState",
    "build_student_graph",
]
