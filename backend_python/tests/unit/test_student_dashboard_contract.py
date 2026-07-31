from datetime import datetime, timedelta

from app.crud.dashboard import get_student_stats
from app.models import Assignment, Class, ClassStudent, Submission


def test_student_dashboard_returns_real_pending_and_draft_assignments(
    db, teacher, student,
):
    classroom = Class(
        name="数据分析班",
        code="DASHBOARD-CLASS",
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

    now = datetime.now()
    common = {
        "teacher_id": teacher.id,
        "teacher_name": teacher.name,
        "classes": [{"id": str(classroom.id), "name": classroom.name}],
        "start_date": now - timedelta(days=1),
        "status": "published",
    }
    todo = Assignment(
        title="即将截止",
        end_date=now + timedelta(hours=2),
        **common,
    )
    draft = Assignment(
        title="继续草稿",
        end_date=now + timedelta(days=2),
        **common,
    )
    reviewed = Assignment(
        title="已经评价",
        end_date=now + timedelta(days=3),
        **common,
    )
    db.add_all([todo, draft, reviewed])
    db.flush()
    db.add_all(
        [
            Submission(
                assignment_id=draft.id,
                student_id=student.id,
                class_id=classroom.id,
                content="草稿",
                status="draft",
                is_draft=True,
            ),
            Submission(
                assignment_id=reviewed.id,
                student_id=student.id,
                class_id=classroom.id,
                content="已提交",
                status="ai_reviewed",
                submitted_at=now,
                ai_score=90,
                is_draft=False,
            ),
        ]
    )
    db.commit()

    result = get_student_stats(db, student.id)

    assert result["pendingAssignments"] == 2
    assert result["completedSubmissions"] == 1
    assert result["pendingAssignmentsList"] == [
        {
            "assignmentId": str(todo.id),
            "title": "即将截止",
            "classId": str(classroom.id),
            "className": "数据分析班",
            "endDate": todo.end_date.isoformat(),
            "status": "not_started",
        },
        {
            "assignmentId": str(draft.id),
            "title": "继续草稿",
            "classId": str(classroom.id),
            "className": "数据分析班",
            "endDate": draft.end_date.isoformat(),
            "status": "draft",
        },
    ]
