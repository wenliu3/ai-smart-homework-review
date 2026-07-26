"""教师图的 ActionDraft 路径（规划阶段 3A.1 / 3A.3）。

安全不变式：
- 图内绝不执行业务写入，只产出草案并落审批。
- 最终审核未通过、运行取消或预算超限时，一律不得落审批。
- approval.required 事件只暴露审批所需的安全字段。
"""
import json

import pytest

from app.agent.contracts import AGENT_BUDGET_EXCEEDED, ReviewResult
from app.agent.graphs.teacher import (
    ACTION_DRAFT_UNAVAILABLE_SUFFIX,
    NO_ACTION_DRAFT_MESSAGE,
    build_teacher_graph,
)
from app.agent.runtime import BudgetExceeded, RunBudget, RunCancelled
from app.agent.tools.approval import create_action_draft

PUBLISH_REQUEST = "帮我发布这份作业"


def _draft():
    return create_action_draft(
        action_type="publish_assignment",
        target_type="assignment",
        target_id="7",
        parameters={
            "assignmentId": 7,
            "beforeSnapshot": {"status": "draft", "title": "第三章作业"},
        },
        summary="发布《第三章作业》",
        risk_level="high",
        ttl_seconds=600,
    )


class FakeActionSpecialists:
    """产出草案并成功落审批的替身。"""

    def __init__(self, draft=_draft, approved=True):
        self._draft = draft
        self._approved = approved
        self.persist_calls = 0

    def teaching_data(self, state):
        return {"candidate_answer": "数据回答"}

    def teaching_strategy(self, state):
        return {"candidate_answer": "策略回答"}

    def action_draft(self, state):
        update = {"candidate_answer": "我已生成发布《第三章作业》的待审批草案。"}
        draft = self._draft() if callable(self._draft) else self._draft
        if draft is not None:
            update["action_draft"] = draft
        return update

    def final_reviewer(self, state):
        if self._approved:
            return {"review": ReviewResult(approved=True, issues=[])}
        return {"review": ReviewResult(approved=False, issues=["越权写操作"])}

    def persist_approval(self, state):
        self.persist_calls += 1
        return {"approval_id": "approval-1"}


class NeverPersistSpecialists(FakeActionSpecialists):
    """任何调用 persist_approval 都视为安全违规。"""

    def persist_approval(self, state):
        raise AssertionError("审核未通过/运行终止时不得落审批")


# ========== 正常路径 ==========

def test_action_draft_path_visits_expected_nodes():
    specialists = FakeActionSpecialists()
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert result["visited_nodes"] == [
        "route",
        "action_draft",
        "final_reviewer",
        "persist_action_draft",
        "finalize",
    ]
    assert result["approval_id"] == "approval-1"
    assert specialists.persist_calls == 1


def test_final_answer_tells_teacher_approval_is_pending():
    graph = build_teacher_graph(FakeActionSpecialists())

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert "审批" in result["final_answer"]


def test_graph_exposes_named_action_nodes():
    graph = build_teacher_graph(FakeActionSpecialists())

    node_names = set(graph.get_graph().nodes)

    assert {"teacher_action_agent", "persist_action_draft"}.issubset(node_names)


# ========== 未产出草案时的兜底 ==========

def test_missing_draft_degrades_with_explicit_message():
    """写意图明确但没产出草案时，显式说明而非静默降级；已有回答不丢弃。"""
    specialists = FakeActionSpecialists(draft=None)
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert "persist_action_draft" not in result["visited_nodes"]
    assert ACTION_DRAFT_UNAVAILABLE_SUFFIX in result["final_answer"]
    assert "我已生成发布《第三章作业》的待审批草案。" in result["final_answer"]
    assert specialists.persist_calls == 0


def test_missing_draft_without_any_answer_falls_back_to_full_message():
    class _SilentSpecialists(FakeActionSpecialists):
        def action_draft(self, state):
            return {"candidate_answer": ""}

    graph = build_teacher_graph(_SilentSpecialists(draft=None))

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert result["final_answer"] == NO_ACTION_DRAFT_MESSAGE


# ========== 安全边界：不得落审批 ==========

def test_rejected_review_never_persists_approval():
    specialists = NeverPersistSpecialists(approved=False)
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert "persist_action_draft" not in result["visited_nodes"]
    assert result.get("approval_id") is None


def test_cancelled_run_stops_before_persist():
    specialists = NeverPersistSpecialists()
    # route / action_draft / final_reviewer 通过，persist 前取消
    checks = iter([False, False, False, True])
    graph = build_teacher_graph(
        specialists,
        budget=RunBudget(),
        is_cancelled=lambda: next(checks),
    )

    with pytest.raises(RunCancelled):
        graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})


def test_budget_exhaustion_stops_before_persist():
    specialists = NeverPersistSpecialists()
    graph = build_teacher_graph(specialists, budget=RunBudget(max_nodes=3))

    with pytest.raises(BudgetExceeded) as exc_info:
        graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert exc_info.value.code == AGENT_BUDGET_EXCEEDED


# ========== approval.required 事件 ==========

def _approval_events(result):
    return [
        event for event in result.get("events", [])
        if event["type"] == "approval.required"
    ]


def test_approval_required_event_carries_only_safe_fields():
    graph = build_teacher_graph(FakeActionSpecialists())

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    events = _approval_events(result)
    assert len(events) == 1
    assert set(events[0]["data"]) == {
        "approval_id",
        "action_type",
        "target_type",
        "target_id",
        "risk_level",
        "summary",
        "expires_at",
    }
    assert events[0]["data"]["approval_id"] == "approval-1"
    assert events[0]["data"]["action_type"] == "publish_assignment"


def test_approval_required_event_leaks_no_internal_details():
    graph = build_teacher_graph(FakeActionSpecialists())

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    serialized = json.dumps(_approval_events(result), ensure_ascii=False)
    for forbidden in (
        "beforeSnapshot",
        "payload_hash",
        "idempotency_key",
        "parameters",
        "teacher_action_agent",
        "persist_action_draft",
    ):
        assert forbidden not in serialized


def test_no_approval_event_when_draft_is_missing():
    graph = build_teacher_graph(FakeActionSpecialists(draft=None))

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert _approval_events(result) == []


# ========== 修订路径不得残留上一轮草案（对抗式审查确认的回归） ==========

class _ReviseSpecialists:
    """第一轮产出草案被驳回；第二轮改为追问、不产出草案。"""

    def __init__(self):
        self.rounds = 0
        self.persisted = []

    def teaching_data(self, state):
        return {"candidate_answer": "数据回答"}

    def teaching_strategy(self, state):
        return {"candidate_answer": "策略回答"}

    def action_draft(self, state):
        self.rounds += 1
        if self.rounds == 1:
            return {
                "candidate_answer": "我将删除《第一份作业》。",
                "action_draft": _draft(),
            }
        return {
            "candidate_answer": "请确认你要删除哪一份作业，我暂时无法生成草案。",
            "limitations": ["作业名称不明确"],
        }

    def final_reviewer(self, state):
        if self.rounds <= 1:
            return {"review": ReviewResult(approved=False, issues=["写操作表述不清"])}
        return {"review": ReviewResult(approved=True, issues=[])}

    def persist_approval(self, state):
        self.persisted.append(state.get("action_draft"))
        return {"approval_id": "approval-stale"}


def test_revision_without_new_draft_never_persists_the_stale_one():
    specialists = _ReviseSpecialists()
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert specialists.rounds == 2
    assert specialists.persisted == []
    assert "persist_action_draft" not in result["visited_nodes"]
    assert result.get("approval_id") is None
    assert _approval_events(result) == []


def test_revision_keeps_the_specialist_followup_answer():
    """草案没生成时也不能丢掉 specialist 已通过审核的追问内容。"""
    specialists = _ReviseSpecialists()
    graph = build_teacher_graph(specialists)

    result = graph.invoke({"user_message": PUBLISH_REQUEST, "visited_nodes": []})

    assert "请确认你要删除哪一份作业" in result["final_answer"]
    assert "草案" in result["final_answer"]
