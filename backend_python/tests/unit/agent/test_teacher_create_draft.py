"""创建作业草稿受控流程（无工具 Agent + 后端解析班级）回归。

保证：
- 创建草稿走 create_assignment_plan（无任何数据库工具）+ 服务端解析班级；
- 不产生 get_my_assignments / get_my_assignment_summary 扇出；
- 最终只产出待审批草案，不写业务库，不包含 assignmentId，target_id 为 None。
"""
from datetime import datetime, timedelta

from app.agent.contracts import (
    ActorContext,
    CreateAssignmentDraftPlan,
    ReviewResult,
)
from app.agent.graphs.teacher import build_teacher_graph
from app.agent.registry import ASSIGNMENT_SUMMARY_RUN_LIMIT, AgentRegistry
from app.agent.runtime import RunBudget
from app.models import Class

CREATE_REQUEST = (
    "请为我名下的「自然语言处理 (NLP)」班级新建一份作业草稿。\n"
    "标题：实验二——语料库分析\n"
    "开始时间：2026-08-27 08:00\n"
    "截止时间：2026-09-03 23:59\n"
    "请帮我补全实验目标、实验内容、操作步骤和提交要求。\n"
    "只生成待审批草稿，不要发布给学生，等我审批后再创建。"
)


def _actor(teacher_id):
    return ActorContext(
        user_id=teacher_id,
        role="teacher",
        request_id="req-create-1",
        session_id="session-create-1",
    )


class _CreateSpecialists:
    """真实图 + 无工具规划 Agent 替身体 + 通过审核 + 落审批替身。"""

    def __init__(self, plan=None, approved=True, persist_id="approval-create-1"):
        self._plan = plan
        self._approved = approved
        self.persist_id = persist_id
        self.persist_calls = 0

    def create_assignment_plan(self, state):
        return {"candidate_plan": self._plan}

    def final_reviewer(self, state):
        if self._approved:
            return {"review": ReviewResult(approved=True, issues=[])}
        return {"review": ReviewResult(approved=False, issues=["越权"])}

    def persist_approval(self, state):
        self.persist_calls += 1
        return {"approval_id": self.persist_id}


def _plan(teacher_class_id):
    return CreateAssignmentDraftPlan(
        className="自然语言处理 (NLP)",
        title="实验二——语料库分析",
        description="实验目标、内容、操作步骤与提交要求。",
        startDate=datetime(2026, 8, 27, 8, 0),
        endDate=datetime(2026, 9, 3, 23, 59),
        allowAttachments=False,
    )


def _make_class(db, teacher, name):
    cls = Class(name=name, code=f"code-{abs(hash(name)) % 10000}", teacher_id=teacher.id)
    db.add(cls)
    db.commit()
    return cls


def test_create_draft_routes_through_plan_and_resolve(db, teacher):
    cls = _make_class(db, teacher, "自然语言处理 (NLP)")
    graph = build_teacher_graph(
        _CreateSpecialists(plan=_plan(cls.id)),
        budget=RunBudget(),
    )

    result = graph.invoke({
        "user_message": CREATE_REQUEST,
        "run_id": "run-create-1",
        "actor": _actor(teacher.id),
        "visited_nodes": [],
    })

    # 全程不触碰历史作业，不扇出摘要：无 get_my_assignments / get_my_assignment_summary
    assert "create_assignment_plan" in result["visited_nodes"]
    assert "get_my_assignments" not in result["visited_nodes"]

    draft = result["action_draft"]
    assert draft.action_type.value == "create_assignment_draft"
    assert draft.target_id is None
    params = draft.parameters
    # 新作业不含 assignmentId；classes 由服务端解析注入，不是模型给的
    assert "assignmentId" not in params
    assert params["classes"] == [cls.id]
    assert params["title"] == "实验二——语料库分析"
    assert params["allowAttachments"] is False
    assert result["approval_id"] == "approval-create-1"
    assert "审批" in result["final_answer"]


def test_create_draft_unresolved_class_produces_no_approval(db, teacher):
    # 当前教师名下没有这个班级
    graph = build_teacher_graph(
        _CreateSpecialists(plan=_plan(0)),
        budget=RunBudget(),
    )

    result = graph.invoke({
        "user_message": CREATE_REQUEST,
        "run_id": "run-create-2",
        "actor": _actor(teacher.id),
        "visited_nodes": [],
    })

    assert result.get("action_draft") is None
    assert result.get("approval_id") is None
    assert "班级" in result["final_answer"]


def test_create_draft_incomplete_plan_produces_no_approval(db, teacher):
    graph = build_teacher_graph(
        _CreateSpecialists(plan=None),
        budget=RunBudget(),
    )

    result = graph.invoke({
        "user_message": "帮我起个作业草稿",
        "run_id": "run-create-3",
        "actor": _actor(teacher.id),
        "visited_nodes": [],
    })

    assert result.get("action_draft") is None
    assert result.get("approval_id") is None


def test_create_plan_forbids_identity_and_class_id_fields():
    """模型不能通过 extra=forbid 之外的字段注入身份/班级 ID。"""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateAssignmentDraftPlan(
            className="自然语言处理 (NLP)",
            title="t",
            description="d",
            startDate=datetime(2026, 1, 1),
            endDate=datetime(2026, 1, 2),
            classId=999,  # 模型伪造的内部 ID 必须被拒绝
        )


def test_create_plan_rejects_inverted_dates():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateAssignmentDraftPlan(
            className="自然语言处理 (NLP)",
            title="t",
            description="d",
            startDate=datetime(2026, 9, 1),
            endDate=datetime(2026, 8, 1),
        )


# ========== 防扇出：创建/写操作/只读工具集合结构 ==========

def test_create_plan_spec_binds_no_tools():
    specs = {s.name: s for s in AgentRegistry.default_specs()}

    assert specs["create_assignment_plan"].tools == ()


def test_teacher_action_tools_exclude_summary_and_student_explorers():
    from app.agent.registry import TEACHER_ACTION_TOOLS

    names = {getattr(t, "name", "") for t in TEACHER_ACTION_TOOLS}
    forbidden = {
        "get_my_assignment_summary",
        "get_my_class_students",
        "get_my_student",
        "get_my_dashboard",
    }
    assert names.isdisjoint(forbidden)


def test_data_agent_has_batch_overview_and_summary_run_limit():
    specs = {s.name: s for s in AgentRegistry.default_specs()}
    data_spec = specs["teaching_data"]
    tool_names = {getattr(t, "name", "") for t in data_spec.tools}

    assert "get_my_assignments_overview" in tool_names
    assert any(
        getattr(m, "tool_name", None) == "get_my_assignment_summary"
        for m in data_spec.middleware
    )
    assert ASSIGNMENT_SUMMARY_RUN_LIMIT == 3


def test_assignments_overview_is_batch_aggregation(db, teacher, user_factory):
    from app.agent.tools.teacher import query_assignments_overview
    from app.models import Assignment, Submission

    cls = _make_class(db, teacher, "NLP")
    student = user_factory("s_overview", "student")
    def _mk(title, statuses):
        a = Assignment(
            title=title, teacher_id=teacher.id, teacher_name=teacher.name,
            classes=[{"id": str(cls.id), "name": cls.name}],
            start_date=datetime.now(), end_date=datetime.now() + timedelta(days=1),
            status="published",
        )
        db.add(a)
        db.commit()
        for s in statuses:
            db.add(Submission(
                assignment_id=a.id, student_id=student.id, class_id=cls.id,
                status=s, submitted_at=datetime.now(),
            ))
        db.commit()
        return a

    _mk("作业一", ["submitted", "ai_reviewed"])
    _mk("作业二", ["teacher_reviewed"])

    result = query_assignments_overview(db, actor_id=teacher.id)

    assert result.status == "ok"
    by_title = {r["title"]: r for r in result.records}
    assert by_title["作业一"]["submissionCount"] == 2
    assert by_title["作业一"]["pendingCount"] == 1
    assert by_title["作业一"]["aiReviewedCount"] == 1
    assert by_title["作业二"]["teacherReviewedCount"] == 1