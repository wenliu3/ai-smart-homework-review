"""教师结构化只读查询的权限与证据测试。"""
from datetime import datetime, timedelta

from app.agent.tools.teaching import query_assignment_summary, query_teacher_classes
from app.models import Assignment, Class


def test_teacher_classes_only_returns_owned_records(db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    db.add_all([
        Class(name="一班", code="C10001", teacher_id=teacher.id, status="active"),
        Class(name="二班", code="C10002", teacher_id=other.id, status="active"),
    ])
    db.commit()

    result = query_teacher_classes(db, actor_id=teacher.id)

    assert result.status == "ok"
    assert [record["name"] for record in result.records] == ["一班"]
    assert result.metrics["classCount"] == 1
    assert result.evidence_refs


def test_assignment_summary_hides_foreign_assignment(db, teacher, user_factory):
    other = user_factory("t_owner", "teacher")
    assignment = Assignment(
        title="其他教师作业",
        teacher_id=other.id,
        teacher_name=other.name,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
    )
    db.add(assignment)
    db.commit()

    result = query_assignment_summary(db, actor_id=teacher.id, assignment_id=assignment.id)

    assert result.status == "not_found"
    assert result.records == []
    assert result.evidence_refs == []
