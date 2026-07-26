"""教师主管 LangGraph 的多 Agent 路由测试。

覆盖：
- 正常路由（数据/策略/写请求）。
- 审核驳回 + 单次修订 -> 通过。
- 二次驳回 -> 安全降级。
- 节点预算超限 -> AGENT_BUDGET_EXCEEDED。
- 结构化事件生成。
- 无界循环防护。
"""
import pytest

from app.agent.contracts import (
    AGENT_BUDGET_EXCEEDED,
    ReviewResult,
    TeacherIntent,
)
from app.agent.graphs.teacher import build_teacher_graph
from app.agent.runtime import BudgetExceeded, RunBudget, RunCancelled
from app.agent.supervisors.teacher import route_teacher_intent


class FakeSpecialists:
    """默认通过的测试替身。"""
    def teaching_data(self, state):
        return {"candidate_answer": "数据回答"}

    def teaching_strategy(self, state):
        return {"candidate_answer": "策略回答"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


def make_controllable_specialists(answer="回答", review_results=None):
    """创建可控替身：review_results 按调用顺序返回审核结果。"""
    review_results = list(review_results or [ReviewResult(approved=True, issues=[])])
    call_log = {"teaching_data": 0, "teaching_strategy": 0, "final_reviewer": 0}

    class _Controllable:
        def teaching_data(self, state):
            call_log["teaching_data"] += 1
            return {"candidate_answer": answer}

        def teaching_strategy(self, state):
            call_log["teaching_strategy"] += 1
            return {"candidate_answer": answer}

        def final_reviewer(self, state):
            call_log["final_reviewer"] += 1
            idx = call_log["final_reviewer"] - 1
            if idx < len(review_results):
                return {"review": review_results[idx]}
            return {"review": ReviewResult(approved=True, issues=[])}

    return _Controllable(), call_log


# ========== 基础路由（现有测试保持不变）==========

def test_data_route_runs_data_agent_then_reviewer():
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    assert result["visited_nodes"] == ["route", "teaching_data", "final_reviewer", "finalize"]
    assert result["final_answer"] == "数据回答"


def test_strategy_route_runs_strategy_agent_then_reviewer():
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "分析最近成绩并给教学建议", "visited_nodes": []})

    assert result["visited_nodes"] == ["route", "teaching_strategy", "final_reviewer", "finalize"]
    assert result["final_answer"] == "策略回答"


def test_unsupported_write_request_never_runs_specialist():
    """白名单外的高风险写请求（删班级/改账号）直接拒绝，不进 specialist。

    受支持的写请求（作业/评分/规则）走 ACTION_DRAFT 路径，
    覆盖见 tests/unit/agent/test_teacher_action_draft.py。
    """
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "帮我删除这个班级", "visited_nodes": []})

    assert result["visited_nodes"] == ["route", "finalize"]
    assert "不在助手可执行范围内" in result["final_answer"]


def test_greeting_routes_to_casual_chat():
    decision = route_teacher_intent("你好啊")

    assert decision.intent == TeacherIntent.CASUAL_CHAT
    assert decision.target_agent == "casual_chat"


def test_greeting_never_runs_teaching_subagents():
    specialists, log = make_controllable_specialists()
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": "你好啊", "visited_nodes": []})

    assert log["teaching_data"] == 0
    assert log["teaching_strategy"] == 0
    assert result["visited_nodes"] == [
        "route",
        "casual_chat",
        "final_reviewer",
        "finalize",
    ]
    assert "你好" in result["final_answer"]


def test_rejected_greeting_never_falls_back_to_teaching_subagent():
    specialists, log = make_controllable_specialists(
        review_results=[
            ReviewResult(approved=False, issues=["普通对话审核拒绝"]),
        ],
    )
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": "你好啊", "visited_nodes": []})

    assert log["teaching_data"] == 0
    assert log["teaching_strategy"] == 0
    assert result["final_answer"] != "回答"


# ========== 审核驳回 + 修订 ==========

def test_first_rejection_triggers_one_revision_then_approve():
    """第一次审核驳回 -> 回退修订 -> 第二次审核通过 -> 正常输出。"""
    specialists, log = make_controllable_specialists(
        answer="修订后回答",
        review_results=[
            ReviewResult(approved=False, issues=["包含敏感信息"]),
            ReviewResult(approved=True, issues=[]),
        ],
    )
    graph = build_teacher_graph(specialists)
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    # specialist 被调用两次（初始 + 修订）
    assert log["teaching_data"] == 2
    # reviewer 被调用两次
    assert log["final_reviewer"] == 2
    assert result["final_answer"] == "修订后回答"
    # 修订路径：route -> data -> review -> data -> review -> finalize
    assert result["visited_nodes"].count("teaching_data") == 2
    assert result["visited_nodes"].count("final_reviewer") == 2
    assert result["visited_nodes"][-1] == "finalize"


def test_second_rejection_triggers_safe_downgrade():
    """二次驳回 -> 安全降级，不再循环。"""
    specialists, log = make_controllable_specialists(
        answer="有问题的回答",
        review_results=[
            ReviewResult(approved=False, issues=["问题1"]),
            ReviewResult(approved=False, issues=["问题2"]),
        ],
    )
    graph = build_teacher_graph(specialists)
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    # specialist 最多被调用两次（初始 + 一次修订），不会无限循环
    assert log["teaching_data"] <= 2
    assert log["final_reviewer"] <= 2
    # 安全降级消息
    assert result["final_answer"] != "有问题的回答"
    assert "暂时" in result["final_answer"] or "无法" in result["final_answer"] or "降级" in result["final_answer"]


def test_revision_count_does_not_exceed_one():
    """修订次数不超过 1 次（revision_count <= 1）。"""
    specialists, log = make_controllable_specialists(
        answer="回答",
        review_results=[
            ReviewResult(approved=False, issues=["问题"]),
            ReviewResult(approved=False, issues=["问题"]),
        ],
    )
    graph = build_teacher_graph(specialists)
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    assert result.get("revision_count", 0) <= 1


# ========== 预算控制 ==========

def test_budget_exceeded_raises_stable_error():
    """节点预算超限时抛出 BudgetExceeded（code=AGENT_BUDGET_EXCEEDED）。"""
    # 设置极小的预算，让节点执行时超限
    budget = RunBudget(max_nodes=2)
    graph = build_teacher_graph(FakeSpecialists(), budget=budget)

    with pytest.raises(BudgetExceeded) as exc_info:
        graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    assert exc_info.value.code == AGENT_BUDGET_EXCEEDED


# ========== 事件生成 ==========

def test_graph_emits_structured_events():
    """图执行生成结构化事件序列。"""
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    events = result.get("events", [])
    event_types = [e["type"] for e in events]

    # 必须包含关键事件
    assert "run.started" in event_types
    assert "route.selected" in event_types
    assert "agent.started" in event_types
    assert "agent.completed" in event_types
    assert "run.completed" in event_types


def test_unsupported_write_emits_route_selected_but_no_agent_events():
    """白名单外的写请求不进入 specialist，不生成 agent.started 事件。"""
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "帮我删除这个学生", "visited_nodes": []})

    events = result.get("events", [])
    event_types = [e["type"] for e in events]

    assert "route.selected" in event_types
    assert "agent.started" not in event_types
    assert "run.completed" in event_types


# ========== 无界循环防护 ==========

def test_no_infinite_loop_on_repeated_rejection():
    """反复驳回不会导致无界循环（最多 specialist 调用 2 次）。"""
    specialists, log = make_controllable_specialists(
        answer="回答",
        review_results=[ReviewResult(approved=False, issues=[f"问题{i}"]) for i in range(100)],
    )
    graph = build_teacher_graph(specialists)
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    # specialist 最多调用 2 次（初始 + 1 次修订）
    assert log["teaching_data"] <= 2
    # 最终一定到达 finalize
    assert result["visited_nodes"][-1] == "finalize"


def test_cancelled_run_stops_before_next_agent():
    specialists, log = make_controllable_specialists()
    checks = iter([False, False, True])
    graph = build_teacher_graph(
        specialists,
        budget=RunBudget(),
        is_cancelled=lambda: next(checks),
    )

    with pytest.raises(RunCancelled):
        graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    assert log["teaching_data"] == 1
    assert log["final_reviewer"] == 0


def test_teacher_graph_exposes_named_supervisor_and_subagent_nodes():
    graph = build_teacher_graph(FakeSpecialists())

    node_names = set(graph.get_graph().nodes)

    assert {
        "teacher_supervisor",
        "teacher_data_agent",
        "teacher_strategy_agent",
        "final_reviewer_agent",
    }.issubset(node_names)
