"""教师多智能体 LangGraph（规格 12 / 13）。

图拓扑：route → specialist → final_reviewer → [persist_action_draft] → finalize
- 审核第一次驳回时回退到原 specialist 修订一次。
- 二次驳回时安全降级，不再循环。
- 受支持的写请求走 teacher_action_agent，只产出待审批草案，图内绝不写业务库；
  审核通过且确实产出草案时才落审批并发 approval.required 事件。
- 每个节点消耗 RunBudget，超限抛出 BudgetExceeded。
- 每个节点追加结构化事件到 state["events"]。
"""
from langgraph.graph import END, START, StateGraph
from langgraph.config import get_stream_writer

from ...crud.action_execution import validate_action_permission
from ...database import SessionLocal
from ..contracts import TeacherIntent
from ..runtime import RunBudget, RunCancelled
from ..supervisors import TeacherSupervisor
from ..tools.approval import create_action_draft
from ..tools.teacher import resolve_class_by_business_name
from .events import append_events, make_event
from .state import TeacherAgentState

# 二次驳回时的安全降级消息
SAFE_DOWNGRADE_MESSAGE = "AI 回答未通过安全审核，暂时无法提供回复，请稍后重试。"
# 白名单之外的高风险写请求（删除班级/学生、改账号等）
UNSUPPORTED_WRITE_MESSAGE = (
    "该写操作不在助手可执行范围内，请到对应管理页面手动完成。"
)
# 写意图明确但没能产出草案时的显式提示：不静默降级成普通分析回答
NO_ACTION_DRAFT_MESSAGE = (
    "这条请求需要审批后执行，但我没能生成可审批的操作草案。"
    "请补充作业名称和具体动作后重试，或改用页面手动操作。"
)
# 草案已落审批时追加给教师的确定性提示（服务端文案，不经模型）
ACTION_DRAFT_PENDING_SUFFIX = "已生成待审批草案，请在「审批」中确认后执行。"
# 有回答但没生成草案时的确定性提示：保留回答内容，同时说清没有可执行草案
ACTION_DRAFT_UNAVAILABLE_SUFFIX = (
    "（本次没有生成可审批的操作草案，如需执行请补充作业名称和具体动作。）"
)
TEACHER_SUPERVISOR_NODE = "teacher_supervisor"
CASUAL_CHAT_NODE = "casual_chat"
TEACHER_DATA_NODE = "teacher_data_agent"
TEACHER_STRATEGY_NODE = "teacher_strategy_agent"
TEACHER_ACTION_NODE = "teacher_action_agent"
CREATE_ASSIGNMENT_PLAN_NODE = "create_assignment_plan"
RESOLVE_ASSIGNMENT_PLAN_NODE = "resolve_assignment_plan"
PERSIST_ACTION_DRAFT_NODE = "persist_action_draft"
FINAL_REVIEWER_NODE = "final_reviewer_agent"

# 创建草稿缺失信息/班级无法解析时的确定性追问（服务端文案，不经模型）
CREATE_PLAN_INCOMPLETE_MESSAGE = (
    "我没能从你的请求中整理出完整的作业信息（班级、标题、时间等），请补充后重试。"
)
CLASS_UNRESOLVED_MESSAGE = (
    "未在当前名下的班级中找到「{class_name}」，或该名称指向多个班级，"
    "请核对班级名称后重试。"
)


def build_teacher_graph(
    specialists,
    budget: RunBudget | None = None,
    is_cancelled=None,
    checkpointer=None,
):
    supervisor = TeacherSupervisor(
        getattr(specialists, "route_classifier", None),
    )

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
            node = TEACHER_DATA_NODE
        elif intent == TeacherIntent.TEACHING_STRATEGY:
            node = TEACHER_STRATEGY_NODE
        elif intent == TeacherIntent.ACTION_DRAFT:
            # 创建草稿走独立的无工具规划流程；其余写操作走 teacher_action Agent。
            # 注意：句子里的「班级」仅描述作业关联对象，不会误判为修改班级。
            if update["intent"].target_agent == "create_assignment_plan_agent":
                node = CREATE_ASSIGNMENT_PLAN_NODE
            else:
                node = TEACHER_ACTION_NODE
        else:
            node = ""
        update["specialist_node"] = node or "finalize"
        update["last_specialist"] = node or TEACHER_DATA_NODE
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

    def action_draft(state):
        """写操作 specialist：只构造待审批草案，绝不执行业务写入。"""
        consume_node()
        emit(make_event("agent.started", {"agent": TEACHER_ACTION_NODE}))
        update = dict(specialists.action_draft(state))
        # 本节点每次执行都必须给出本轮草案：action_draft 是 last-value 通道，
        # 缺键时上一轮被驳回的旧草案会残留下来，被 after_review 当作本轮结果落审批。
        update.setdefault("action_draft", None)
        emit(make_event("agent.completed", {"agent": TEACHER_ACTION_NODE}))
        update["visited_nodes"] = [*state.get("visited_nodes", []), "action_draft"]
        return _with_events(state, update,
            make_event("agent.started", {"agent": TEACHER_ACTION_NODE}),
            make_event("agent.completed", {"agent": TEACHER_ACTION_NODE}),
        )

    def create_assignment_plan(state):
        """创建作业草稿规划：无工具 LLM 产出结构化业务计划，绝不查询数据库。"""
        consume_node()
        emit(make_event("agent.started", {"agent": CREATE_ASSIGNMENT_PLAN_NODE}))
        update = dict(specialists.create_assignment_plan(state))
        update.setdefault("candidate_plan", None)
        emit(make_event("agent.completed", {"agent": CREATE_ASSIGNMENT_PLAN_NODE}))
        update["visited_nodes"] = [
            *state.get("visited_nodes", []), CREATE_ASSIGNMENT_PLAN_NODE,
        ]
        return _with_events(state, update,
            make_event("agent.started", {"agent": CREATE_ASSIGNMENT_PLAN_NODE}),
            make_event("agent.completed", {"agent": CREATE_ASSIGNMENT_PLAN_NODE}),
        )

    def resolve_assignment_plan(state):
        """后端确定性解析：按业务名称解析班级、校验归属、签名待审批草案。"""
        consume_node()
        plan = state.get("candidate_plan")
        teacher_id = state["actor"].user_id
        run_id = state.get("run_id", "")
        base_update = {
            "visited_nodes": [
                *state.get("visited_nodes", []), RESOLVE_ASSIGNMENT_PLAN_NODE,
            ],
        }

        def unresolved(candidate_answer: str):
            return _with_events(state, {
                **base_update,
                "candidate_answer": candidate_answer,
                "evidence_refs": [],
                "action_draft": None,
            }, make_event("create.class.unresolved", {}))

        if plan is None:
            return _with_events(state, {
                **base_update,
                "candidate_answer": CREATE_PLAN_INCOMPLETE_MESSAGE,
                "evidence_refs": [],
                "action_draft": None,
            }, make_event("create.plan.incomplete", {}))

        with SessionLocal() as db:
            resolution = resolve_class_by_business_name(db, teacher_id, plan.class_name)
            if resolution.status != "ok":
                return unresolved(
                    CLASS_UNRESOLVED_MESSAGE.format(class_name=plan.class_name),
                )
            parameters = {
                "title": plan.title,
                "description": plan.description,
                "classes": [resolution.class_id],
                "startDate": plan.start_date.isoformat(),
                "endDate": plan.end_date.isoformat(),
                "allowAttachments": plan.allow_attachments,
            }
            try:
                validate_action_permission(
                    "create_assignment_draft",
                    parameters,
                    teacher_id,
                    "teacher",
                    db,
                )
            except ValueError:
                return _with_events(state, {
                    **base_update,
                    "candidate_answer": "创建作业草案校验未通过，请核对班级归属后重试。",
                    "evidence_refs": [],
                    "action_draft": None,
                }, make_event("create.validation.rejected", {}))
            draft = create_action_draft(
                action_type="create_assignment_draft",
                target_type="assignment",
                target_id=None,
                parameters=parameters,
                summary=(
                    f"为班级「{resolution.name}」创建作业草稿《{plan.title}》"
                ),
                risk_level="medium",
                idempotency_seed=f"teacher:{teacher_id}:{run_id}",
            )
        update = {
            **base_update,
            "action_draft": draft,
            "candidate_answer": (
                f"已为班级「{resolution.name}」生成作业草稿《{plan.title}》"
                f"（{plan.start_date:%Y-%m-%d %H:%M} 至 "
                f"{plan.end_date:%Y-%m-%d %H:%M}）的待审批草案。"
            ),
            "evidence_refs": [
                f"server://classes/{resolution.class_id}?resolved=server",
            ],
        }
        emit(make_event("create.plan.resolved", {
            "class_name": resolution.name,
            "class_id": resolution.class_id,
        }))
        return _with_events(state, update,
            make_event("create.plan.resolved", {
                "class_name": resolution.name,
                "class_id": resolution.class_id,
            }),
        )

    def persist_action_draft(state):
        """审核通过后落待审批记录，并通知前端有草案待确认。"""
        consume_node()
        update = dict(specialists.persist_approval(state))
        update["visited_nodes"] = [
            *state.get("visited_nodes", []), PERSIST_ACTION_DRAFT_NODE,
        ]
        approval_id = update.get("approval_id")
        if not approval_id:
            return _with_events(state, update)
        draft = state["action_draft"]
        # 只暴露审批所需字段：parameters/快照/哈希留在审批详情接口后面
        event = make_event("approval.required", {
            "approval_id": approval_id,
            "action_type": draft.action_type.value,
            "target_type": draft.target_type,
            "target_id": draft.target_id,
            "risk_level": draft.risk_level.value,
            "summary": draft.summary,
            "expires_at": draft.expires_at.isoformat(),
        })
        emit(event)
        return _with_events(state, update, event)

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
        review = state.get("review")
        if intent == TeacherIntent.UNSUPPORTED_WRITE:
            answer = UNSUPPORTED_WRITE_MESSAGE
        elif review and not review.approved:
            answer = SAFE_DOWNGRADE_MESSAGE
        elif intent == TeacherIntent.ACTION_DRAFT:
            # 写请求必须以「草案已落审批」收尾，否则显式说明而非静默降级。
            # 但没落草案时不能丢掉 specialist 已通过审核的内容（常是「还缺哪些信息」
            # 的追问），只在其后追加一句确定性说明。
            candidate = state.get("candidate_answer", "").rstrip()
            if state.get("approval_id"):
                suffix = ACTION_DRAFT_PENDING_SUFFIX
            else:
                suffix = ACTION_DRAFT_UNAVAILABLE_SUFFIX
            if candidate:
                answer = f"{candidate}\n\n{suffix}"
            else:
                answer = (
                    ACTION_DRAFT_PENDING_SUFFIX
                    if state.get("approval_id")
                    else NO_ACTION_DRAFT_MESSAGE
                )
        else:
            answer = state.get("candidate_answer", "")
        return _with_events(state,
            {"final_answer": answer, "visited_nodes": [*state.get("visited_nodes", []), "finalize"]},
            make_event("run.completed", {"final_answer_length": len(answer)}),
        )

    def select_specialist(state):
        intent = state["intent"].intent
        if intent == TeacherIntent.ACTION_DRAFT:
            # ACTION_DRAFT 下按路由选定的子节点（创建草稿 vs 其他写操作）
            return state.get("specialist_node", TEACHER_ACTION_NODE)
        return intent.value

    def after_review(state):
        review = state["review"]
        revision_count = state.get("revision_count", 0)
        if review.approved:
            # 只有审核通过且确实产出草案时才落审批
            if state.get("action_draft") is not None:
                return PERSIST_ACTION_DRAFT_NODE
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
    graph.add_node(TEACHER_ACTION_NODE, action_draft)
    graph.add_node(CREATE_ASSIGNMENT_PLAN_NODE, create_assignment_plan)
    graph.add_node(RESOLVE_ASSIGNMENT_PLAN_NODE, resolve_assignment_plan)
    graph.add_node(FINAL_REVIEWER_NODE, final_reviewer)
    graph.add_node(PERSIST_ACTION_DRAFT_NODE, persist_action_draft)
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
            TEACHER_ACTION_NODE: TEACHER_ACTION_NODE,
            CREATE_ASSIGNMENT_PLAN_NODE: CREATE_ASSIGNMENT_PLAN_NODE,
            TeacherIntent.UNSUPPORTED_WRITE.value: "finalize",
        },
    )
    graph.add_edge(CASUAL_CHAT_NODE, FINAL_REVIEWER_NODE)
    graph.add_edge(TEACHER_DATA_NODE, FINAL_REVIEWER_NODE)
    graph.add_edge(TEACHER_STRATEGY_NODE, FINAL_REVIEWER_NODE)
    graph.add_edge(TEACHER_ACTION_NODE, FINAL_REVIEWER_NODE)
    graph.add_edge(CREATE_ASSIGNMENT_PLAN_NODE, RESOLVE_ASSIGNMENT_PLAN_NODE)
    graph.add_edge(RESOLVE_ASSIGNMENT_PLAN_NODE, FINAL_REVIEWER_NODE)
    graph.add_conditional_edges(
        FINAL_REVIEWER_NODE,
        after_review,
        {
            "finalize": "finalize",
            "revise": "revise",
            PERSIST_ACTION_DRAFT_NODE: PERSIST_ACTION_DRAFT_NODE,
        },
    )
    graph.add_edge(PERSIST_ACTION_DRAFT_NODE, "finalize")
    graph.add_conditional_edges("revise", after_revise)
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
