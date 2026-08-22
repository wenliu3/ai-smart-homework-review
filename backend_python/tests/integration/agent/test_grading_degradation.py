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
from app.agent.tools.content import normalize_submission_content
from app.crud import agent_run as agent_run_crud
from app.crud.agent_run import (
    GRADING_STALE_SECONDS,
    create_run,
    finalize_stale_grading_runs,
)
from app.crud.agent_session import create_session
from app.crud.submission import apply_ai_grading_result
from app.models import AgentArtifact, AgentRun, Assignment, Submission
from app.tasks import grading as grading_tasks
from app.tasks.grading import enqueue_grading_job, execute_grading_job
from app.tasks.grading_request import mark_grading_timeout_from_request


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
                "error": "GradingDraft 校验失败：缺少评分维度 items",
                "raw_response": "模型原始输出留证",
            },
            "usage": {},
            "model_usage": {},
            "visited_nodes": ["normalize_submission_content", "grading_agent"],
        },
    )
    db.refresh(submission)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()

    # run 是「完成并转人工」，不是失败
    assert result["status"] == "completed"
    assert run.status == "completed"
    assert run.error_code is None
    # 原始全文留证供排查
    artifact = assistant_db.query(AgentArtifact).filter(
        AgentArtifact.run_id == run_id,
        AgentArtifact.artifact_type == "grading_raw_draft",
    ).one()
    assert "校验失败" in str(artifact.payload_json)
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
    """作业要求、教师参考附件与学生正文都进入批改图初始状态。"""
    (tmp_path / "reference.txt").write_text("参考答案要点", encoding="utf-8")
    assignment, submission = _setup(
        db, student,
        description="<p>请论述软件测试的意义</p>",
        attachments=[{
            "fileName": "reference.txt",
            "fileUrl": "/uploads/reference.txt",
            "fileType": "text/plain",
        }],
    )

    state = grading_tasks.build_grading_state(
        submission,
        assignment,
        grading_tasks.rubric_from_ai_rule(assignment.ai_rule),
        upload_dir=str(tmp_path),
        routing={"rule_model_code": "deepseek", "rule_prompt": ""},
    )

    # 作业要求（原文进入 description）+ 参考附件文本进入参考资料
    assert "请论述软件测试的意义" in state["assignment_description"]
    assert "参考答案要点" in state["reference_materials"]
    # 学生正文进入规范化内容
    normalized = normalize_submission_content(
        rich_text=submission.content or "",
        attachments=submission.attachments or [],
        upload_dir=str(tmp_path),
    )
    assert any("学生答案" in block.content for block in normalized.text_blocks)


# ========== 任务 7：硬超时父进程收口与历史僵尸 Run ==========

def _stale_grading_run(
    assistant_db,
    student,
    *,
    status="processing",
    age_seconds=GRADING_STALE_SECONDS + 20,
    intent="grading",
):
    """构造指定状态/启动时间/意图的批改 run（可独立于真实任务队列）。"""
    session = create_session(
        assistant_db,
        user_id=student.id,
        actor_role="student",
        session_id="grading-stale-0001",
    )
    run = create_run(assistant_db, session.id, user_id=student.id, intent=intent)
    assistant_db.query(AgentRun).filter(AgentRun.id == run.id).update(
        {
            AgentRun.status: status,
            AgentRun.started_at: datetime.now() - timedelta(seconds=age_seconds),
        },
        synchronize_session=False,
    )
    assistant_db.commit()
    return run


def test_hard_timeout_request_finalizes_run(
    db, assistant_db, student, monkeypatch,
):
    """Celery 父进程硬超时收口：running run → failed/AGENT_GRADING_TIMEOUT。"""
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "running"

    mark_grading_timeout_from_request({"run_id": run.id, "user_id": student.id})

    assistant_db.refresh(run)
    assert run.status == "failed"
    assert run.error_code == AGENT_GRADING_TIMEOUT


def test_hard_timeout_request_is_idempotent(
    db, assistant_db, student, monkeypatch,
):
    """重复收口幂等：第二次调用不再改写状态。"""
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()

    mark_grading_timeout_from_request({"run_id": run.id, "user_id": student.id})
    mark_grading_timeout_from_request({"run_id": run.id, "user_id": student.id})

    assistant_db.refresh(run)
    assert run.status == "failed"
    assert run.error_code == AGENT_GRADING_TIMEOUT


@pytest.mark.parametrize("terminal_status", ["completed", "cancelled"])
def test_hard_timeout_request_keeps_terminal_runs(
    db, assistant_db, student, monkeypatch, terminal_status,
):
    """已终态的 run 不被硬超时收口覆盖。"""
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    run.status = terminal_status
    assistant_db.commit()

    mark_grading_timeout_from_request({"run_id": run.id, "user_id": student.id})

    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert persisted.status == terminal_status
    assert persisted.error_code is None


def test_hard_timeout_request_finalizes_processing_run(
    db, assistant_db, student, monkeypatch,
):
    """真实硬超时时 run 已被 claim 为 processing，钩子同样应收口。"""
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)
    assistant_db.query(AgentRun).filter(AgentRun.id == run_id).update(
        {AgentRun.status: "processing"},
        synchronize_session=False,
    )
    assistant_db.commit()

    mark_grading_timeout_from_request({"run_id": run_id, "user_id": student.id})

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "failed"
    assert run.error_code == AGENT_GRADING_TIMEOUT


def test_hard_timeout_request_swallows_fail_run_exception(
    db, assistant_db, student, monkeypatch,
):
    """收口清理异常绝不向上抛，不遮盖 Celery 原始超时失败。"""
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)

    def _boom(db_, run_id_, user_id_, error_code):
        raise RuntimeError("assistant db write failed")

    monkeypatch.setattr(agent_run_crud, "fail_run", _boom)

    # 不应抛异常，正常返回
    mark_grading_timeout_from_request({"run_id": run_id, "user_id": student.id})

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "running"


def test_hard_timeout_request_skips_missing_payload(
    db, assistant_db, student, monkeypatch,
):
    """缺 run_id/user_id 的 payload 被跳过，不抛异常也不改库。"""
    _, submission = _setup(db, student)
    run_id = _enqueue(db, assistant_db, student, submission, monkeypatch)

    mark_grading_timeout_from_request({})
    mark_grading_timeout_from_request({"run_id": run_id})
    mark_grading_timeout_from_request({"user_id": student.id})

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "running"
    assert run.error_code is None


def test_grading_stale_threshold_exceeds_hard_time_limit():
    """承重不变量：僵尸收口阈值必须大于 Celery 硬超时 time_limit，
    否则读取时收口会先于父进程硬超时把仍在跑的 run 误标失败。"""
    assert GRADING_STALE_SECONDS > grading_tasks.run_grading_task.time_limit


def test_stale_grading_run_finalized_on_read(assistant_db, student):
    """超阈值僵尸 processing 批改 run 在读取时收口为 failed/AGENT_GRADING_TIMEOUT。"""
    run = _stale_grading_run(assistant_db, student)

    closed = finalize_stale_grading_runs(assistant_db, user_id=student.id)

    assert closed == 1
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == "failed"
    assert persisted.error_code == AGENT_GRADING_TIMEOUT
    assert persisted.finished_at is not None


def test_stale_grading_run_finalized_without_owner_filter(assistant_db, student):
    """不传 user_id 时收口任意归属的僵尸批改 run。"""
    run = _stale_grading_run(assistant_db, student)

    closed = finalize_stale_grading_runs(assistant_db)

    assert closed == 1
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == "failed"
    assert persisted.error_code == AGENT_GRADING_TIMEOUT


def test_stale_finalize_is_idempotent(assistant_db, student):
    """僵尸收口幂等：第二次调用不产生额外更新。"""
    run = _stale_grading_run(assistant_db, student)

    assert finalize_stale_grading_runs(assistant_db, user_id=student.id) == 1
    assert finalize_stale_grading_runs(assistant_db, user_id=student.id) == 0
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == "failed"
    assert persisted.error_code == AGENT_GRADING_TIMEOUT


@pytest.mark.parametrize(
    "status",
    ["running", "completed", "failed", "cancelled"],
)
def test_stale_grading_run_keeps_non_processing_status(
    assistant_db, student, status,
):
    """非 processing 状态（即使超阈值）不被收口。"""
    run = _stale_grading_run(assistant_db, student, status=status)

    closed = finalize_stale_grading_runs(assistant_db, user_id=student.id)

    assert closed == 0
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == status


def test_fresh_processing_grading_run_not_finalized(assistant_db, student):
    """阈值内的新鲜 processing run 保持原状。"""
    run = _stale_grading_run(assistant_db, student, age_seconds=60)

    closed = finalize_stale_grading_runs(assistant_db, user_id=student.id)

    assert closed == 0
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == "processing"


def test_stale_non_grading_intent_not_finalized(assistant_db, student):
    """非批改意图的僵尸 run 不收口。"""
    run = _stale_grading_run(assistant_db, student, intent="teacher_query")

    closed = finalize_stale_grading_runs(assistant_db, user_id=student.id)

    assert closed == 0
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == "processing"


def test_stale_run_of_other_owner_not_finalized(
    assistant_db, student, user_factory,
):
    """传 user_id 时只收口该归属的 run，他人僵尸 run 不动。"""
    other = user_factory("t_other", "teacher")
    run = _stale_grading_run(assistant_db, student)

    closed = finalize_stale_grading_runs(assistant_db, user_id=other.id)

    assert closed == 0
    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert persisted.status == "processing"
