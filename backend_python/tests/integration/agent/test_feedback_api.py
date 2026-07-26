"""反馈闭环（规划阶段 4.3）。

- POST /assistant/runs/{run_id}/feedback：用户 👍/👎，同 run 重复反馈 upsert。
- 教师改分自动采集与 AI 评分的差值（跨库尽力而为，失败不阻塞批改）。
"""
from datetime import datetime, timedelta

import pytest

from app.crud import agent_run, correcting as correcting_crud
from app.crud.agent_session import create_session
from app.models import AgentFeedback, Assignment, Class, Submission


@pytest.fixture()
def own_run(assistant_db, teacher):
    session = create_session(
        assistant_db, user_id=teacher.id, actor_role="teacher",
    )
    run = agent_run.create_run(
        assistant_db, session_id=session.id, user_id=teacher.id, intent="pending",
    )
    agent_run.finalize_run(
        assistant_db, run.id, teacher.id, final_output="回答完成。",
    )
    return run


def _post(client, headers, run_id, body):
    return client.post(
        f"/api/assistant/runs/{run_id}/feedback", headers=headers, json=body,
    )


# ========== 用户评分 ==========

def test_submit_feedback_persists_user_rating(
    client, assistant_db, teacher, auth_header, own_run,
):
    response = _post(
        client, auth_header(teacher), own_run.id,
        {"rating": 1, "comment": "回答很有帮助"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["rating"] == 1
    row = assistant_db.query(AgentFeedback).one()
    assert row.run_id == own_run.id
    assert row.user_id == teacher.id
    assert row.source == "user_rating"
    assert row.rating == 1
    assert row.comment == "回答很有帮助"


def test_feedback_is_idempotent_upsert(
    client, assistant_db, teacher, auth_header, own_run,
):
    headers = auth_header(teacher)
    _post(client, headers, own_run.id, {"rating": 1})
    _post(client, headers, own_run.id, {"rating": -1})

    rows = assistant_db.query(AgentFeedback).all()
    assert len(rows) == 1
    assert rows[0].rating == -1


def test_feedback_rejects_malformed_run_id(client, teacher, auth_header):
    response = _post(
        client, auth_header(teacher), "not-a-run", {"rating": 1},
    )

    assert response.status_code == 400


def test_feedback_cross_user_returns_404(
    client, user_factory, auth_header, own_run,
):
    other = user_factory("t_fb_other", "teacher")

    response = _post(client, auth_header(other), own_run.id, {"rating": 1})

    assert response.status_code == 404


def test_feedback_rejects_invalid_rating(
    client, teacher, auth_header, own_run,
):
    response = _post(client, auth_header(teacher), own_run.id, {"rating": 0})

    assert response.status_code == 422


def test_feedback_rejects_system_session_run(
    client, assistant_db, student, auth_header,
):
    create_session(
        assistant_db,
        user_id=student.id,
        actor_role="student",
        session_id="grading-feedback-guard-01",
    )
    run = agent_run.create_run(
        assistant_db,
        session_id="grading-feedback-guard-01",
        user_id=student.id,
        intent="grading",
    )

    response = _post(client, auth_header(student), run.id, {"rating": 1})

    assert response.status_code == 400


# ========== 教师改分差值自动采集 ==========

@pytest.fixture()
def graded_submission_with_run(db, assistant_db, teacher, student):
    session = create_session(
        assistant_db,
        user_id=student.id,
        actor_role="student",
        session_id="grading-correction-src-01",
    )
    run = agent_run.create_run(
        assistant_db, session_id=session.id, user_id=student.id, intent="grading",
    )
    klass = Class(name="反馈班", code="FBCLS", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    assignment = Assignment(
        title="反馈作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(klass.id), "name": klass.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
        ai_rule={"maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=klass.id,
        status="ai_reviewed",
        submission_count=1,
        ai_score=80,
        grading_run_id=run.id,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission, run


def test_teacher_review_records_score_delta(
    db, assistant_db, teacher, graded_submission_with_run,
):
    submission, run = graded_submission_with_run

    correcting_crud.submit_teacher_review(
        db,
        submission_id=submission.id,
        teacher_score=90,
        teacher_review_content="整体不错",
        actor_user_id=teacher.id,
    )

    row = assistant_db.query(AgentFeedback).one()
    assert row.run_id == run.id
    assert row.source == "teacher_correction"
    assert row.ai_score == 80
    assert row.teacher_score == 90
    assert row.score_delta == 10
    assert row.user_id == teacher.id


def test_repeat_correction_upserts_single_row(
    db, assistant_db, teacher, graded_submission_with_run,
):
    submission, _ = graded_submission_with_run

    for score in (90, 85):
        correcting_crud.submit_teacher_review(
            db,
            submission_id=submission.id,
            teacher_score=score,
            teacher_review_content="改分",
            actor_user_id=teacher.id,
        )

    rows = assistant_db.query(AgentFeedback).all()
    assert len(rows) == 1
    assert rows[0].teacher_score == 85
    assert rows[0].score_delta == 5


def test_no_feedback_without_grading_run(
    db, assistant_db, teacher, graded_submission_with_run,
):
    submission, _ = graded_submission_with_run
    submission.grading_run_id = None
    db.commit()

    correcting_crud.submit_teacher_review(
        db,
        submission_id=submission.id,
        teacher_score=88,
        teacher_review_content="改分",
        actor_user_id=teacher.id,
    )

    assert assistant_db.query(AgentFeedback).count() == 0


def test_feedback_failure_never_breaks_review(
    db, teacher, graded_submission_with_run, monkeypatch,
):
    submission, _ = graded_submission_with_run

    def boom():
        raise RuntimeError("PG unavailable")

    monkeypatch.setattr(correcting_crud, "AssistantSessionLocal", boom)

    result = correcting_crud.submit_teacher_review(
        db,
        submission_id=submission.id,
        teacher_score=92,
        teacher_review_content="改分",
        actor_user_id=teacher.id,
    )

    assert result["success"] is True
    db.refresh(submission)
    assert submission.teacher_score == 92
