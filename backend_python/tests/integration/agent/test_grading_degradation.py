"""批改任务层的失败降级与上下文接线（规划阶段 3B.1 / 3B.2 / 3B.3）。

不变式：
- 结构化失败/预算耗尽 → 转教师人工（run 完成 + 原始草案留证），不是 run 失败。
- 软超时 → 稳定错误码 AGENT_GRADING_TIMEOUT。
- 教师端提示带上机器可读的复核原因。
- 提交行记录 grading_run_id，供教师/学生两侧查询进度与产物。
"""
from datetime import datetime, timedelta

import pytest

from app.agent.contracts import (
    AGENT_GRADING_TIMEOUT,
    CriterionGrade,
    GradingDraft,
    GradingOutcome,
)
from app.agent.runtime import BudgetExceeded
from app.crud.submission import apply_ai_grading_result
from app.models import AgentArtifact, AgentRun, Assignment, Submission
from app.tasks import grading as grading_tasks
from app.tasks.grading import enqueue_grading_job, execute_grading_job


def _setup(db, student, *, description="", attachments=None):
    assignment = Assignment(
        title="测试作业",
        description=description,
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"version": "rubric-v3", "maxScore": 100},
        attachments=attachments or [],
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=2,
        content="学生答案",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return assignment, submission


def _enqueue(db, assistant_db, student, submission, monkeypatch):
    monkeypatch.setattr(
        grading_tasks.run_grading_task, "delay", lambda **kwargs: None,
    )
    return enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )


def _execute(db, assistant_db, student, submission, run_id, runner):
    return execute_grading_job(
        submission_id=submission.id,
        submission_count=2,
        rubric_version="rubric-v3",
        run_id=run_id,
        user_id=student.id,
        business_db=db,
        run_db=assistant_db,
        workflow_runner=runner,
    )


# ========== 结构化失败转人工 ==========

def test_grading_failure_degrades_to_manual_review(
    db, assistant_db, student, monkeypatch,
):
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)

    result = _execute(
        db, assistant_db, student, submission, run_id,
        lambda *_: {
            "grading_failure": {
                "stage": "grading_agent",
                "error": "评分项必须与量表完整且唯一对应",
                "raw_response": '{"items": "broken"}',
            },
            "visited_nodes": [
                "normalize_submission_content", "grading_agent",
            ],
        },
    )
    db.refresh(submission)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()

    # run 是「完成并转人工」，不是失败
    assert result["status"] == "completed"
    assert run.status == "completed"
    assert run.error_code is None
    # 原始草案留证供排查
    artifact = assistant_db.query(AgentArtifact).filter(
        AgentArtifact.run_id == run_id,
        AgentArtifact.artifact_type == "grading_raw_draft",
    ).one()
    assert "broken" in str(artifact.payload_json)
    # 教师端拿到明确提示；不写入任何分数
    assert submission.ai_score is None
    assert "人工" in submission.ai_review_content
    assert submission.status == "submitted"


def test_budget_exhaustion_also_degrades_to_manual_review(
    db, assistant_db, student, monkeypatch,
):
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)

    def runner(*_):
        raise BudgetExceeded("模型调用次数超过限制")

    result = _execute(
        db, assistant_db, student, submission, run_id, runner,
    )
    db.refresh(submission)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()

    assert result["status"] == "completed"
    assert run.status == "completed"
    assert submission.ai_score is None
    assert "人工" in submission.ai_review_content


def test_soft_time_limit_marks_run_with_stable_timeout_code(
    db, assistant_db, student, monkeypatch,
):
    from celery.exceptions import SoftTimeLimitExceeded

    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)

    def runner(*_):
        raise SoftTimeLimitExceeded()

    with pytest.raises(SoftTimeLimitExceeded):
        _execute(db, assistant_db, student, submission, run_id, runner)

    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "failed"
    assert run.error_code == AGENT_GRADING_TIMEOUT


# ========== 复核原因到教师端 ==========

def test_review_reasons_reach_teacher_note(db, student):
    _, submission = _setup(db, student)
    primary = GradingDraft(
        rubric_version="rubric-v3",
        items=[CriterionGrade(
            criterion_id="quality",
            title="质量",
            score=88,
            max_score=100,
            feedback="完成良好",
            evidence_refs=["submission:text:1"],
        )],
        summary="总体完成良好",
    )
    outcome = GradingOutcome(
        primary=primary,
        review=primary.model_copy(deep=True),
        score_difference=0,
        needs_human_review=True,
        review_reasons=["主批改评分缺少提交证据：quality"],
    )

    applied = apply_ai_grading_result(
        db,
        submission_id=submission.id,
        expected_submission_count=2,
        outcome=outcome,
    )
    db.refresh(submission)

    assert applied is True
    assert "主批改评分缺少提交证据" in submission.ai_review_content


# ========== grading_run_id 接线 ==========

def test_enqueue_writes_grading_run_id_to_submission(
    db, assistant_db, student, monkeypatch,
):
    _, submission = _setup(db, student)

    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)
    db.refresh(submission)

    assert submission.grading_run_id == run_id


# ========== 上下文注入 ==========

def test_grading_state_includes_assignment_context(db, student, tmp_path):
    (tmp_path / "reference.txt").write_text("参考答案要点", encoding="utf-8")
    assignment, submission = _setup(
        db, student,
        description="请论述软件测试的意义",
        attachments=[{
            "fileName": "reference.txt",
            "fileUrl": "/uploads/reference.txt",
            "fileType": "text/plain",
        }],
    )
    monkeypatch_upload = tmp_path

    state = grading_tasks.build_grading_state(
        submission,
        assignment,
        grading_tasks.rubric_from_ai_rule(assignment.ai_rule),
        upload_dir=monkeypatch_upload,
    )

    assert state["assignment_description"] == "请论述软件测试的意义"
    assert "参考答案要点" in state["reference_materials"]
    assert state["runtime_budget"].max_model_calls == 6
    assert state["submission_id"] == submission.id
