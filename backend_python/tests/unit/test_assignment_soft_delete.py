"""作业软删语义（规划阶段 3A.2 / 决策 D1）。

不变式：软删作业对所有读路径必须与硬删等价不可见，
但提交记录保留以便误删后恢复。
"""
from datetime import datetime, timedelta

import pytest

from app.agent.tools import admin as admin_tools
from app.agent.tools import student as student_tools
from app.agent.tools import teacher as teacher_tools
from app.core.exceptions import NotFoundException
from app.crud import assignment as assignment_crud
from app.crud import dashboard as dashboard_crud
from app.models import Assignment, Class, ClassStudent, Submission


@pytest.fixture()
def published_assignment(db, teacher, student):
    """一份已发布作业 + 班级 + 学生的一条提交记录。"""
    klass = Class(name="soft-del", code="SOFTDEL", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    db.add(ClassStudent(
        class_id=klass.id, student_id=student.id, status="active",
    ))
    assignment = Assignment(
        title="待删除作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(klass.id), "name": klass.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=klass.id,
        status="submitted",
    )
    db.add(submission)
    db.commit()
    return assignment


def test_delete_marks_deleted_at_instead_of_removing_row(
    db, teacher, published_assignment,
):
    result = assignment_crud.delete_assignment(
        db, published_assignment.id, teacher.id,
    )

    assert result == {"message": "删除成功"}
    row = db.query(Assignment).filter(
        Assignment.id == published_assignment.id,
    ).first()
    assert row is not None
    assert row.deleted_at is not None


def test_delete_keeps_submissions_for_recovery(
    db, teacher, published_assignment,
):
    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    remaining = db.query(Submission).filter(
        Submission.assignment_id == published_assignment.id,
    ).count()
    assert remaining == 1


def test_soft_deleted_assignment_disappears_from_teacher_list(
    db, teacher, published_assignment,
):
    assert assignment_crud.get_teacher_assignments(db, teacher.id, {})["total"] == 1

    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    assert assignment_crud.get_teacher_assignments(db, teacher.id, {})["total"] == 0


def test_soft_deleted_assignment_detail_is_not_found(
    db, teacher, published_assignment,
):
    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    with pytest.raises(NotFoundException):
        assignment_crud.get_teacher_detail(db, published_assignment.id)


def test_soft_deleted_assignment_disappears_for_student(
    db, teacher, student, published_assignment,
):
    before = assignment_crud.get_student_assignments(db, student.id, None)
    assert before["total"] == 1

    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    after = assignment_crud.get_student_assignments(db, student.id, None)
    assert after["total"] == 0
    stats = assignment_crud.get_student_statistics(db, student.id, None)
    assert stats["totalAssignments"] == 0


def test_second_delete_is_rejected(db, teacher, published_assignment):
    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    with pytest.raises(NotFoundException):
        assignment_crud.delete_assignment(
            db, published_assignment.id, teacher.id,
        )


def test_soft_deleted_assignment_is_invisible_to_agent_tools(
    db, teacher, student, published_assignment,
):
    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    assert teacher_tools.query_teacher_assignments(
        db, actor_id=teacher.id,
    ).metrics.get("assignmentCount", 0) == 0
    assert teacher_tools.query_assignment_summary(
        db, actor_id=teacher.id, assignment_id=published_assignment.id,
    ).status == "not_found"
    assert teacher_tools.query_teacher_dashboard(
        db, actor_id=teacher.id,
    ).metrics.get("assignmentCount", 0) == 0
    assert teacher_tools.query_pending_reviews(
        db, actor_id=teacher.id,
    ).metrics.get("pendingCount", 0) == 0
    assert student_tools.query_my_learning_overview(
        db, actor_id=student.id,
    ).metrics.get("submissionCount", 0) == 0
    assert admin_tools.query_platform_operations(db).metrics[
        "assignmentCount"
    ] == 0


def test_soft_deleted_assignment_disappears_from_dashboards(
    db, teacher, published_assignment,
):
    assignment_crud.delete_assignment(db, published_assignment.id, teacher.id)

    assert dashboard_crud.get_admin_overview(db)["totalAssignments"] == 0
    teacher_stats = dashboard_crud.get_teacher_stats(db, teacher.id)
    assert teacher_stats["myAssignments"] == 0
    assert teacher_stats["pendingReviews"] == 0
    assert dashboard_crud.get_teacher_pending_tasks(db, teacher.id)[
        "assignments"
    ] == []
