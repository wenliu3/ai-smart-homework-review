from datetime import datetime, timedelta

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.crud import assignment as assignment_crud
from app.crud import submission as submission_crud
from app.models import Assignment, Class, ClassStudent


def _grant_assignment_access(db, teacher, student):
    classroom = Class(
        name="测试班级",
        code="ACCESS-CLASS",
        teacher_id=teacher.id,
        status="active",
    )
    db.add(classroom)
    db.flush()
    db.add(
        ClassStudent(
            class_id=classroom.id,
            student_id=student.id,
            status="active",
        )
    )
    db.flush()
    return classroom


def test_get_my_submission_includes_assignment_attachment_contract(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    attachments = [
        {
            "fileName": "参考答案.pdf",
            "fileUrl": "/uploads/reference.pdf",
            "fileSize": 1024,
            "fileType": "application/pdf",
        },
    ]
    assignment = Assignment(
        title="附件作业",
        description="请阅读教师附件后完成作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        attachments=attachments,
        allow_attachments=True,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    result = submission_crud.get_my_submission(
        db, assignment_id=assignment.id, student_id=student.id,
    )

    assert result["assignment"]["attachments"] == attachments
    assert result["assignment"]["allowAttachments"] is True


def test_get_my_submission_normalizes_nullable_assignment_attachment_fields(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    assignment = Assignment(
        title="旧数据作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        attachments=None,
        allow_attachments=None,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    result = submission_crud.get_my_submission(
        db, assignment_id=assignment.id, student_id=student.id,
    )

    assert result["assignment"]["attachments"] == []
    assert result["assignment"]["allowAttachments"] is False


def test_student_cannot_read_submission_detail_for_another_class(
    db, teacher, student,
):
    classroom = Class(
        name="其他班级",
        code="OTHER-CLASS",
        teacher_id=teacher.id,
        status="active",
    )
    db.add(classroom)
    db.flush()
    assignment = Assignment(
        title="不可见作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        attachments=[{"fileName": "内部资料.pdf", "fileUrl": "/uploads/private.pdf"}],
        allow_attachments=True,
    )
    db.add(assignment)
    db.commit()

    with pytest.raises(BadRequestException, match="不属于该作业班级"):
        submission_crud.get_my_submission(db, assignment.id, student.id)


def test_student_cannot_read_assignment_detail_for_another_class(
    db, teacher, student,
):
    classroom = Class(
        name="其他班级",
        code="OTHER-DETAIL-CLASS",
        teacher_id=teacher.id,
        status="active",
    )
    db.add(classroom)
    db.flush()
    assignment = Assignment(
        title="不可见作业详情",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        attachments=[{"fileName": "内部资料.pdf", "fileUrl": "/uploads/private.pdf"}],
    )
    db.add(assignment)
    db.commit()

    with pytest.raises(BadRequestException, match="不属于该作业班级"):
        assignment_crud.get_student_detail(db, assignment.id, student.id)


def test_submit_rejects_attachments_when_teacher_disabled_them(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    assignment = Assignment(
        title="仅正文作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        allow_attachments=False,
    )
    db.add(assignment)
    db.commit()

    with pytest.raises(BadRequestException, match="不允许上传附件"):
        submission_crud.submit(
            db,
            student.id,
            {
                "assignmentId": assignment.id,
                "classId": classroom.id,
                "content": "正文",
                "attachments": [
                    {
                        "fileName": "绕过前端.pdf",
                        "fileUrl": "",
                        "fileSize": 1,
                        "fileType": "application/pdf",
                    }
                ],
            },
        )


def test_submit_without_attachments_still_works_when_teacher_disabled_them(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    assignment = Assignment(
        title="仅正文作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        allow_attachments=False,
    )
    db.add(assignment)
    db.commit()

    result = submission_crud.submit(
        db,
        student.id,
        {
            "assignmentId": assignment.id,
            "classId": classroom.id,
            "content": "只提交正文",
            "attachments": [],
        },
    )

    assert result.attachments == []


def test_student_cannot_read_unpublished_assignment_even_with_membership(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    assignment = Assignment(
        title="教师草稿",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="draft",
        attachments=[{"fileName": "草稿资料.pdf", "fileUrl": "/uploads/draft.pdf"}],
    )
    db.add(assignment)
    db.commit()

    with pytest.raises(NotFoundException, match="作业不存在"):
        submission_crud.get_my_submission(db, assignment.id, student.id)
