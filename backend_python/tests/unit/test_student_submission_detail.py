from datetime import datetime, timedelta

from app.crud import submission as submission_crud
from app.models import Assignment


def test_get_my_submission_includes_assignment_attachment_contract(
    db, teacher, student,
):
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
        classes=[],
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
    assignment = Assignment(
        title="旧数据作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[],
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
