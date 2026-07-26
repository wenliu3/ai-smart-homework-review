"""GET /assistant/runs/{run_id}/artifacts 权限矩阵（规划阶段 3B.3）。

权限：run 归属人（学生本人）可读；该提交的任课教师经
submission → assignment → teacher 跨库校验后可读；其他人 404。
"""
from datetime import datetime, timedelta

import pytest

from app.crud import agent_run, agent_session
from app.models import Assignment, Submission


@pytest.fixture()
def grading_run(db, assistant_db, teacher, student):
    """一次已完成的批改 run：run 归属学生，提交行记录 grading_run_id。"""
    assignment = Assignment(
        title="产物作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
        ai_rule={"version": "v1", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()

    session = agent_session.create_session(
        assistant_db,
        user_id=student.id,
        actor_role="student",
        session_id="grading-artifact-test-0001",
        title="批改任务",
    )
    run = agent_run.create_run(
        assistant_db,
        session_id=session.id,
        user_id=student.id,
        intent="grading",
        graph_version="grading-v1",
    )
    agent_run.finalize_run(
        assistant_db,
        run.id,
        student.id,
        final_output="批改完成。",
        artifacts=[{
            "artifact_type": "grading_outcome",
            "schema_version": "v1",
            "payload": {"primary": {"summary": "总体完成良好"}},
        }],
    )

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="ai_reviewed",
        submission_count=1,
        grading_run_id=run.id,
    )
    db.add(submission)
    db.commit()
    return run, submission, assignment


def _get(client, headers, run_id):
    return client.get(
        f"/api/assistant/runs/{run_id}/artifacts", headers=headers,
    )


def test_run_owner_can_read_artifacts(
    client, student, auth_header, grading_run,
):
    run, _, _ = grading_run

    response = _get(client, auth_header(student), run.id)

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["artifactType"] == "grading_outcome"
    assert items[0]["payload"]["primary"]["summary"] == "总体完成良好"


def test_assignment_teacher_can_read_student_grading_artifacts(
    client, teacher, auth_header, grading_run,
):
    run, _, _ = grading_run

    response = _get(client, auth_header(teacher), run.id)

    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) == 1


def test_unrelated_teacher_gets_404(
    client, user_factory, auth_header, grading_run,
):
    run, _, _ = grading_run
    other = user_factory("t_artifact_other", "teacher")

    assert _get(client, auth_header(other), run.id).status_code == 404


def test_other_student_gets_404(
    client, user_factory, auth_header, grading_run,
):
    run, _, _ = grading_run
    peer = user_factory("s_artifact_peer", "student")

    assert _get(client, auth_header(peer), run.id).status_code == 404


def test_teacher_access_is_blocked_when_assignment_soft_deleted(
    client, db, teacher, auth_header, grading_run,
):
    """作业软删后教师链路断开；run 归属人不受影响。"""
    run, _, assignment = grading_run
    assignment.deleted_at = datetime.now()
    db.commit()

    assert _get(client, auth_header(teacher), run.id).status_code == 404


def test_malformed_run_id_is_rejected(client, teacher, auth_header):
    response = client.get(
        "/api/assistant/runs/not-a-run/artifacts",
        headers=auth_header(teacher),
    )

    assert response.status_code == 400
