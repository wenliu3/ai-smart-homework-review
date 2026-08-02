from datetime import datetime, timedelta

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.crud import assignment as assignment_crud
from app.crud import submission as submission_crud
from app.models import Assignment, Class, ClassStudent, Submission


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


def test_get_my_submission_preserves_ai_rule_max_score_snapshot(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    ai_rule = {
        "id": "9",
        "name": "实验报告规则",
        "modelType": "mimo",
        "prompt": "按实验要求评分",
        "maxScore": 60,
    }
    assignment = Assignment(
        title="结构化批改作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule=ai_rule,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    result = submission_crud.get_my_submission(
        db, assignment_id=assignment.id, student_id=student.id,
    )

    assert result["assignment"]["aiRule"]["maxScore"] == 60
    assert result["assignment"]["rawMaxScore"] == 60


def test_get_my_submission_defaults_ai_rule_max_score_to_100(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    old_ai_rule = {
        "id": "9",
        "name": "实验报告规则",
        "modelType": "mimo",
        "prompt": "按实验要求评分",
    }
    assignment = Assignment(
        title="旧数据作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule=old_ai_rule,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    result = submission_crud.get_my_submission(
        db, assignment_id=assignment.id, student_id=student.id,
    )

    assert result["assignment"]["aiRule"].get("maxScore", 100) == 100
    assert result["assignment"]["rawMaxScore"] == 100


def test_get_my_submission_returns_ai_review_dimension_items(
    db, teacher, student,
):
    classroom = _grant_assignment_access(db, teacher, student)
    assignment = Assignment(
        title="多维度批改作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={
            "id": "9",
            "name": "多维度规则",
            "modelType": "mimo",
            "prompt": "按维度评分",
            "maxScore": 100,
            "criteria": [
                {"id": "content", "title": "内容完整性", "maxScore": 60},
                {"id": "expression", "title": "表达规范", "maxScore": 40},
            ],
        },
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=classroom.id,
        status="ai_reviewed",
        submission_count=1,
        ai_score=88,
        ai_review_content="总体完成良好",
        ai_review_items=[
            {
                "criterion_id": "content",
                "title": "内容完整性",
                "score": 54,
                "max_score": 60,
                "feedback": "要点齐全，示例充分",
                "evidence_refs": ["submission:text:1"],
            },
            {
                "criterion_id": "expression",
                "title": "表达规范",
                "score": 34,
                "max_score": 40,
                "feedback": "个别语句不通顺",
                "evidence_refs": [],
            },
        ],
    )
    db.add(submission)
    db.commit()

    result = submission_crud.get_my_submission(
        db, assignment_id=assignment.id, student_id=student.id,
    )

    assert result["aiReview"]["score"] == 88
    assert result["aiReview"]["items"] == [
        {
            "criterionId": "content",
            "title": "内容完整性",
            "score": 54,
            "maxScore": 60,
            "feedback": "要点齐全，示例充分",
            "evidenceRefs": ["submission:text:1"],
        },
        {
            "criterionId": "expression",
            "title": "表达规范",
            "score": 34,
            "maxScore": 40,
            "feedback": "个别语句不通顺",
            "evidenceRefs": [],
        },
    ]


def test_get_my_submission_ai_review_items_is_none_when_missing(
    db, teacher, student,
):
    """单维度/旧数据没有分项：aiReview.items 应为 None，前端保持纯文本展示。"""
    classroom = _grant_assignment_access(db, teacher, student)
    assignment = Assignment(
        title="单维度批改作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(classroom.id), "name": classroom.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"id": "9", "modelType": "mimo", "prompt": "整体评分", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=classroom.id,
        status="ai_reviewed",
        submission_count=1,
        ai_score=90,
        ai_review_content="整体不错",
    )
    db.add(submission)
    db.commit()

    result = submission_crud.get_my_submission(
        db, assignment_id=assignment.id, student_id=student.id,
    )

    assert result["aiReview"]["items"] is None


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
