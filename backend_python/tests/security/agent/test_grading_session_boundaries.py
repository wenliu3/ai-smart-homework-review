"""系统批改会话的安全边界。

批改任务会话（session_id 以 "grading-" 开头，由 tasks/grading.py 生成）
属于系统内部运行记录：
- 不得出现在用户会话列表（GET /assistant/sessions）。
- 不得对其发起对话（POST /assistant/runs/stream 返回 400）。
- 其运行不得被用户取消（否则学生可借取消逃避 AI 批改）。
"""
from datetime import datetime, timedelta

from app.models import AgentRun, Assignment, Submission
from app.tasks import grading as grading_tasks
from app.tasks.grading import enqueue_grading_job

SESSIONS_URL = "/api/assistant/sessions"


def _make_grading_run(db, assistant_db, student, monkeypatch, title="边界测试作业"):
    """走真实入队路径创建批改会话与运行，返回 run_id。"""
    assignment = Assignment(
        title=title,
        description="",
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"version": "rubric-v1", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=1,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    monkeypatch.setattr(
        grading_tasks.run_grading_task,
        "delay",
        lambda **kwargs: None,
    )
    return enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )


def test_student_cannot_cancel_own_grading_run(
    client, db, assistant_db, student, auth_header, monkeypatch,
):
    run_id = _make_grading_run(db, assistant_db, student, monkeypatch)

    resp = client.post(
        f"/api/assistant/runs/{run_id}/cancel",
        headers=auth_header(student),
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 10011
    # 运行未被取消，批改结果仍可正常写回
    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "running"


def test_grading_session_hidden_from_session_list(
    client, db, assistant_db, student, auth_header, monkeypatch,
):
    _make_grading_run(db, assistant_db, student, monkeypatch)
    # 学生自己的正常会话仍应可见
    created = client.post(
        SESSIONS_URL,
        json={"title": "正常会话"},
        headers=auth_header(student),
    )
    normal_id = created.json()["data"]["sessionId"]

    resp = client.get(SESSIONS_URL, headers=auth_header(student))

    assert resp.status_code == 200
    ids = [s["sessionId"] for s in resp.json()["data"]["sessions"]]
    assert normal_id in ids
    assert not any(sid.startswith("grading-") for sid in ids)


def test_stream_rejects_grading_session(
    client, db, assistant_db, student, auth_header, monkeypatch,
):
    run_id = _make_grading_run(db, assistant_db, student, monkeypatch)
    session_id = assistant_db.query(AgentRun).filter(
        AgentRun.id == run_id,
    ).one().session_id
    assert session_id.startswith("grading-")
    assistant_db.rollback()  # 释放 sqlite 读锁，避免阻塞后续请求

    resp = client.post(
        "/api/assistant/runs/stream",
        json={"message": "hi", "session_id": session_id},
        headers=auth_header(student),
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 10011
