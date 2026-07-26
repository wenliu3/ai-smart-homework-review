"""软删引入的回归（2026-07-26 对抗式审查确认）。

两条不变式：
- 软删作业的提交不得再出现在批改队列，也不得被继续打分。
- 删除用户的前置守卫必须按外键实际残留计数（含软删作业），
  否则会留下 teacher_id 指向已删用户的孤儿行。
"""
from datetime import datetime, timedelta

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.crud import assignment as assignment_crud
from app.crud import correcting as correcting_crud
from app.crud import user as user_crud
from app.models import Assignment, Class, Submission


@pytest.fixture()
def graded_submission(db, teacher, student):
    klass = Class(name="批改班", code="CORRCLS", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    assignment = Assignment(
        title="待删作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(klass.id), "name": klass.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
        ai_rule={"maxScore": 50},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=klass.id,
        status="submitted",
        content="学生正文",
        ai_score=40,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return assignment, submission


def test_soft_deleted_assignment_submissions_leave_grading_queue(
    db, teacher, graded_submission,
):
    assignment, _ = graded_submission
    assert correcting_crud.get_submission_list(db, {})["total"] == 1

    assignment_crud.delete_assignment(db, assignment.id, teacher.id)

    assert correcting_crud.get_submission_list(db, {})["total"] == 0


def test_soft_deleted_assignment_submission_detail_is_not_found(
    db, teacher, graded_submission,
):
    assignment, submission = graded_submission
    assignment_crud.delete_assignment(db, assignment.id, teacher.id)

    with pytest.raises(NotFoundException):
        correcting_crud.get_submission_detail(db, submission.id)


def test_soft_deleted_assignment_submission_cannot_be_graded(
    db, teacher, graded_submission,
):
    """否则「已删除」的作业还会继续产生批改数据，且无法清理。"""
    assignment, submission = graded_submission
    assignment_crud.delete_assignment(db, assignment.id, teacher.id)

    with pytest.raises(NotFoundException):
        correcting_crud.submit_teacher_review(
            db,
            submission_id=submission.id,
            teacher_score=45,
            teacher_review_content="不该写进去",
        )

    db.expire_all()
    assert db.query(Submission).filter(
        Submission.id == submission.id,
    ).first().teacher_score is None


def test_delete_user_guard_counts_soft_deleted_assignments(
    db, teacher, graded_submission,
):
    """守卫按外键残留计数：软删作业仍占着 teacher_id 外键，不能放行删除。"""
    assignment, _ = graded_submission
    assignment_crud.delete_assignment(db, assignment.id, teacher.id)
    # 班级转移走，只剩软删作业挡着
    db.query(Class).filter(Class.teacher_id == teacher.id).delete()
    db.commit()

    with pytest.raises(BadRequestException):
        user_crud.delete_user(db, teacher.id)

    db.expire_all()
    remaining = db.query(Assignment).filter(
        Assignment.teacher_id == teacher.id,
    ).count()
    assert remaining == 1


def test_batch_delete_user_guard_counts_soft_deleted_assignments(
    db, teacher, graded_submission,
):
    assignment, _ = graded_submission
    assignment_crud.delete_assignment(db, assignment.id, teacher.id)
    db.query(Class).filter(Class.teacher_id == teacher.id).delete()
    db.commit()

    result = user_crud.delete_users_batch(db, [teacher.id])

    assert result["successCount"] == 0
    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.teacher_id == teacher.id,
    ).count() == 1
