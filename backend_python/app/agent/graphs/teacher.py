"""教师只读多智能体 LangGraph（规格 12 / 13）。

图拓扑：route → specialist → final_reviewer → finalize
- 审核第一次驳回时回退到原 specialist 修订一次。
- 二次驳回时安全降级，不再循环。
- 每个节点消耗 RunBudget，超限抛出 BudgetExceeded。
- 每个节点追加结构化事件到 state["events"]。
"""
from langgraph.graph import END, START, StateGraph
from langgraph.config import get_stream_writer

from ..contracts import TeacherIntent
from ..runtime import RunBudget, RunCancelled
from ..supervisors import TeacherSupervisor
from .events import append_events, make_event
from .state import TeacherAgentState

# 二次驳回时的安全降级消息
SAFE_DOWNGRADE_MESSAGE = "AI 回答未通过安全审核，暂时无法提供回复，请稍后重试。"
READ_ONLY_MESSAGE = "当前 Agent 仅支持只读查询，暂不能执行发布、修改或删除操作。"
TEACHER_SUPERVISOR_NODE = "teacher_supervisor"
CASUAL_CHAT_NODE = "casual_chat"
TEACHER_DATA_NODE = "teacher_data_agent"
TEACHER_STRATEGY_NODE = "teacher_strategy_agent"
FINAL_REVIEWER_NODE = "final_reviewer_agent"


def build_teacher_graph(
    specialists,
    budget: RunBudget | None = None,
    is_cancelled=None,
    checkpointer=None,
):
    supervisor = TeacherSupervisor()

    def consume_node():
        if is_cancelled is not None and is_cancelled():
            raise RunCancelled("Agent 运行已取消")
        if budget is not None:
            budget.consume_node()

    def _with_events(state, update, *events):
        """合并节点更新与事件。"""
        update = dict(update)
        update.update(append_events(state, *events))
        return update

    def emit(event):
        """通过 LangGraph custom stream 实时发送事件；invoke 模式下安全忽略。"""
        try:
            get_stream_writer()(event)
        except RuntimeError:
            pass

    def route(state):
        consume_node()
        update = supervisor.route(state)
        intent = update["intent"].intent
        if intent == TeacherIntent.TEACHING_DATA:
            update["last_specialist"] = TEACHER_DATA_NODE
        elif intent == TeacherIntent.TEACHING_STRATEGY:
            update["last_specialist"] = TEACHER_STRATEGY_NODE
        update["visited_nodes"] = [*state.get("visited_nodes", []), "route"]
        emit(make_event("route.selected", {"intent": intent.value}))
        return _with_events(state, update,
            make_event("run.started"),
            make_event("route.selected", {"intent": intent.value}),
        )

    def teaching_data(state):
        consume_node()
        emit(make_event("agent.started", {"agent": TEACHER_DATA_NODE}))
        update = specialists.teaching_data(state)
        emit(make_event("agent.completed", {"agent": TEACHER_DATA_NODE}))
        update["visited_nodes"] = [*state.get("visited_nodes", []), "teaching_data"]
        return _with_events(state, update,
            make_event("agent.started", {"agent": TEACHER_DATA_NODE}),
            make_event("agent.completed", {"agent": TEACHER_DATA_NODE}),
        )

    def casual_chat(state):
        consume_node()
        return _with_events(
            state,
            {
                "candidate_answer": (
                    "你好，我是 AI 教学助手。"
                    "我可以帮你查询教学数据、分析教学情况并提供教学策略建议。"
                ),
                "evidence_refs": [],
                "limitations": [],
                "visited_nodes": [*state.get("visited_nodes", []), "casual_chat"],
            },
        )

    def teaching_strategy(state):
        consume_node()
        emit(make_event("agent.started", {"agent": TEACHER_STRATEGY_NODE}))
        update = specialists.teaching_strategy(state)
        emit(make_event("agent.completed", {"agent": TEACHER_STRATEGY_NODE}))
        update["visited_nodes"] = [*state.get("visited_nodes", []), "teaching_strategy"]
        return _with_events(state, update,
            make_event("agent.started", {"agent": TEACHER_STRATEGY_NODE}),
            make_event("agent.completed", {"agent": TEACHER_STRATEGY_NODE}),
        )

    def final_reviewer(state):
        consume_node()
        emit(make_event("agent.started", {"agent": FINAL_REVIEWER_NODE}))
        update = specialists.final_reviewer(state)
        emit(make_event("agent.completed", {"agent": FINAL_REVIEWER_NODE}))
        update["visited_nodes"] = [*state.get("visited_nodes", []), "final_reviewer"]
        return _with_events(state, update,
            make_event("agent.started", {"agent": FINAL_REVIEWER_NODE}),
            make_event("agent.completed", {"agent": FINAL_REVIEWER_NODE}),
        )

    def revise(state):
        consume_node()
        revision_count = state.get("revision_count", 0) + 1
        emit(make_event("route.selected", {
            "reason": "revision",
            "count": revision_count,
        }))
        return _with_events(state,
            {"revision_count": revision_count, "visited_nodes": [*state.get("visited_nodes", []), "revise"]},
            make_event("route.selected", {"reason": "revision", "count": revision_count}),
        )

    def finalize(state):
        consume_node()
        intent = state["intent"].intent
        if intent == TeacherIntent.UNSUPPORTED_WRITE:
            answer = READ_ONLY_MESSAGE
        else:
            review = state.get("review")
            if review and not review.approved:
                answer = SAFE_DOWNGRADE_MESSAGE
            else:
                answer = state.get("candidate_answer", "")
        return _with_events(state,
            {"final_answer": answer, "visited_nodes": [*state.get("visited_nodes", []), "finalize"]},
            make_event("run.completed", {"final_answer_length": len(answer)}),
        )

    def select_specialist(state):
        return state["intent"].intent.value

    def after_review(state):
        review = state["review"]
        revision_count = state.get("revision_count", 0)
        if review.approved:
            return "finalize"
        if state["intent"].intent == TeacherIntent.CASUAL_CHAT:
            return "finalize"
        if revision_count >= 1:
            return "finalize"  # 安全降级
        return "revise"  # 第一次驳回，回退修订

    def after_revise(state):
        return state.get("last_specialist", TEACHER_DATA_NODE)

    graph = StateGraph(TeacherAgentState)
    graph.add_node(TEACHER_SUPERVISOR_NODE, route)
    graph.add_node(CASUAL_CHAT_NODE, casual_chat)
    graph.add_node(TEACHER_DATA_NODE, teaching_data)
    graph.add_node(TEACHER_STRATEGY_NODE, teaching_strategy)
    graph.add_node(FINAL_REVIEWER_NODE, final_reviewer)
    graph.add_node("revise", revise)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, TEACHER_SUPERVISOR_NODE)
    graph.add_conditional_edges(
        TEACHER_SUPERVISOR_NODE,
        select_specialist,
        {
            TeacherIntent.CASUAL_CHAT.value: CASUAL_CHAT_NODE,
            TeacherIntent.TEACHING_DATA.value: TEACHER_DATA_NODE,
            TeacherIntent.TEACHING_STRATEGY.value: TEACHER_STRATEGY_NODE,
            TeacherIntent.UNSUPPORTED_WRITE.value: "finalize",
        },
    )
    graph.add_edge(CASUAL_CHAT_NODE, FINAL_REVIEWER_NODE)
    graph.add_edge(TEACHER_DATA_NODE, FINAL_REVIEWER_NODE)
    graph.add_edge(TEACHER_STRATEGY_NODE, FINAL_REVIEWER_NODE)
    graph.add_conditional_edges(
        FINAL_REVIEWER_NODE,
        after_review,
        {"finalize": "finalize", "revise": "revise"},
    )
    graph.add_conditional_edges("revise", after_revise)
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
