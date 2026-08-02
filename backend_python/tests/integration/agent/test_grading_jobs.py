from datetime import datetime, timedelta

import pytest

from app.agent.contracts import (
    AGENT_RULE_MODEL_NOT_CONFIGURED,
)
from app.crud import ai_model as ai_model_crud
from app.crud.submission import apply_ai_grading_result
from app.models import Submission
from app.models import AgentArtifact, AgentRun, Assignment
from app.tasks import grading as grading_tasks
from app.tasks.grading import (
    GradingRoutingError,
    build_grading_idempotency_key,
    enqueue_grading_job,
    execute_grading_job,
)
from tests.factories import _outcome


def test_grading_idempotency_key_is_stable_and_versioned():
    assert build_grading_idempotency_key(12, 3, "rubric-v3") == (
        "grading:submission:12:version:3:rubric:rubric-v3"
    )
    assert build_grading_idempotency_key(12, 4, "rubric-v3") != (
        build_grading_idempotency_key(12, 3, "rubric-v3")
    )


def test_old_grading_job_cannot_overwrite_new_submission_or_teacher_fields(db):
    submission = Submission(
        assignment_id=1,
        student_id=2,
        class_id=3,
        status="teacher_reviewed",
        submission_count=2,
        teacher_score=95,
        teacher_review_content="教师最终评价",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    applied = apply_ai_grading_result(
        db,
        submission_id=submission.id,
        expected_submission_count=1,
        outcome=_outcome(),
    )
    db.refresh(submission)

    assert applied is False
    assert submission.ai_score is None
    assert submission.teacher_score == 95
    assert submission.teacher_review_content == "教师最终评价"


def test_current_grading_job_updates_only_ai_fields(db):
    submission = Submission(
        assignment_id=1,
        student_id=2,
        class_id=3,
        status="teacher_reviewed",
        submission_count=2,
        teacher_score=95,
        teacher_review_content="教师最终评价",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    applied = apply_ai_grading_result(
        db,
        submission_id=submission.id,
        expected_submission_count=2,
        outcome=_outcome(),
    )
    db.refresh(submission)

    assert applied is True
    assert submission.ai_score == 88
    assert submission.ai_review_content == "总体完成良好"
    assert submission.ai_review_items == [
        {
            "criterion_id": "quality",
            "title": "质量",
            "score": 88.0,
            "max_score": 100.0,
            "feedback": "完成良好",
            "evidence_refs": ["submission:text:1"],
        }
    ]
    assert submission.status == "teacher_reviewed"
    assert submission.teacher_score == 95
    assert submission.teacher_review_content == "教师最终评价"


def test_enqueue_is_idempotent_for_same_submission_version(
    db, assistant_db, student, monkeypatch,
):
    assignment = Assignment(
        title="测试作业",
        description="",
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"version": "v1", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=2,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    dispatched = []
    monkeypatch.setattr(
        grading_tasks.run_grading_task,
        "delay",
        lambda **kwargs: dispatched.append(kwargs),
    )

    first = enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )
    second = enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )

    assert first == second
    assert len(dispatched) == 1
    assert dispatched[0]["run_id"] == first


def test_execute_job_persists_steps_artifact_and_version_safe_result(
    db, assistant_db, student, monkeypatch,
):
    assignment = Assignment(
        title="测试作业",
        description="",
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"version": "rubric-v3", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=2,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    monkeypatch.setattr(
        grading_tasks.run_grading_task,
        "delay",
        lambda **kwargs: None,
    )
    run_id = enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )

    result = execute_grading_job(
        submission_id=submission.id,
        submission_count=2,
        rubric_version="rubric-v3",
        run_id=run_id,
        user_id=student.id,
        business_db=db,
        run_db=assistant_db,
        workflow_runner=lambda *_: {
            "outcome": _outcome(),
            "visited_nodes": [
                "normalize_submission_content",
                "grading_agent",
                "grading_review_agent",
                "grading_decision",
            ],
        },
    )
    db.refresh(submission)
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()

    assert result["status"] == "completed"
    assert submission.ai_score == 88
    assert run.status == "completed"
    assert [step.node_name for step in run.steps] == [
        "normalize_submission_content",
        "grading_agent",
        "grading_review_agent",
        "grading_decision",
    ]
    artifact = assistant_db.query(AgentArtifact).filter(
        AgentArtifact.run_id == run_id,
    ).one()
    assert artifact.artifact_type == "grading_outcome"


def test_processing_job_redelivery_recovers_and_completes(
    db, assistant_db, student, monkeypatch,
):
    assignment = Assignment(
        title="重投递测试作业",
        description="",
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"version": "rubric-v3", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=2,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    monkeypatch.setattr(
        grading_tasks.run_grading_task,
        "delay",
        lambda **kwargs: None,
    )
    run_id = enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )
    assistant_db.query(AgentRun).filter(AgentRun.id == run_id).update(
        {AgentRun.status: "processing"},
        synchronize_session=False,
    )
    assistant_db.commit()

    result = execute_grading_job(
        submission_id=submission.id,
        submission_count=2,
        rubric_version="rubric-v3",
        run_id=run_id,
        user_id=student.id,
        business_db=db,
        run_db=assistant_db,
        workflow_runner=lambda *_: {
            "outcome": _outcome(),
            "visited_nodes": [],
        },
    )

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert result["status"] == "completed"
    assert run.status == "completed"


def test_processing_job_execution_error_marks_run_failed(
    db, assistant_db, student, monkeypatch,
):
    assignment = Assignment(
        title="异常状态测试作业",
        description="",
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"version": "rubric-v3", "maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=2,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    monkeypatch.setattr(
        grading_tasks.run_grading_task,
        "delay",
        lambda **kwargs: None,
    )
    run_id = enqueue_grading_job(
        db,
        assistant_db,
        submission=submission,
        user_id=student.id,
        actor_role="student",
    )

    with pytest.raises(RuntimeError, match="grading crashed"):
        execute_grading_job(
            submission_id=submission.id,
            submission_count=2,
            rubric_version="rubric-v3",
            run_id=run_id,
            user_id=student.id,
            business_db=db,
            run_db=assistant_db,
            workflow_runner=lambda *_: (_ for _ in ()).throw(
                RuntimeError("grading crashed"),
            ),
        )

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.status == "failed"
    assert run.error_code == "AGENT_GRADING_FAILED"


@pytest.mark.parametrize("terminal_status", ["completed", "cancelled", "failed"])
def test_terminal_grading_job_redelivery_keeps_existing_status(
    assistant_db, student, terminal_status,
):
    from app.crud.agent_run import create_run
    from app.crud.agent_session import create_session

    session = create_session(
        assistant_db,
        user_id=student.id,
        actor_role="student",
        session_id=f"terminal-{terminal_status}",
    )
    run = create_run(
        assistant_db,
        session.id,
        user_id=student.id,
        intent="grading",
    )
    assistant_db.query(AgentRun).filter(AgentRun.id == run.id).update(
        {AgentRun.status: terminal_status},
        synchronize_session=False,
    )
    assistant_db.commit()

    result = execute_grading_job(
        submission_id=1,
        submission_count=1,
        rubric_version="rubric-v3",
        run_id=run.id,
        user_id=student.id,
        run_db=assistant_db,
        workflow_runner=lambda *_: pytest.fail("终态任务不应重新执行"),
    )

    assistant_db.expire_all()
    persisted = assistant_db.query(AgentRun).filter(AgentRun.id == run.id).one()
    assert result["status"] == terminal_status
    assert persisted.status == terminal_status


# ========== 任务 6：任务层选择双路径（显式运行配置） ==========

def _routing_assignment(*, with_model_type: bool = True) -> Assignment:
    ai_rule = {"version": "v1", "maxScore": 100, "prompt": "按实验要求评分"}
    if with_model_type:
        ai_rule["modelType"] = "mimo"
    return Assignment(
        title="路由测试作业",
        description="",
        teacher_id=99,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule=ai_rule,
    )


def test_routing_config_uses_ai_rule_model_type(db):
    """单 Agent：rule_model_code 只来自 ai_rule.modelType，不含独立结构化绑定。"""
    db.add(_routing_assignment())
    db.commit()

    routing = grading_tasks._grading_routing_config(db, db.query(Assignment).one())

    assert routing == {
        "rule_model_code": "mimo",
        "rule_prompt": "按实验要求评分",
    }


def test_routing_config_stable_across_default_switch(db, ai_model_factory):
    """切换默认模型后 rule_model_code 不变（不依赖默认模型）。"""
    ai_model_factory(code="mimo", is_default=True)
    ai_model_factory(code="deepseek", is_default=False)
    db.add(_routing_assignment())
    db.commit()

    before = grading_tasks._grading_routing_config(db, db.query(Assignment).one())
    ai_model_crud.set_default(db, "deepseek")
    after = grading_tasks._grading_routing_config(db, db.query(Assignment).one())

    assert before["rule_model_code"] == "mimo"
    assert after["rule_model_code"] == "mimo"


def test_routing_config_missing_rule_model_fails_controlled(db):
    """缺少 ai_rule.modelType：任务在模型调用前以稳定错误码受控失败。"""
    db.add(_routing_assignment(with_model_type=False))
    db.commit()

    with pytest.raises(GradingRoutingError) as exc_info:
        grading_tasks._grading_routing_config(db, db.query(Assignment).one())

    assert exc_info.value.code == AGENT_RULE_MODEL_NOT_CONFIGURED


def test_grading_state_carries_explicit_routing(db, student):
    """build_grading_state 把规则模型路由写入初始状态。"""
    db.add(_routing_assignment())
    db.commit()
    assignment = db.query(Assignment).one()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
        submission_count=2,
    )
    db.add(submission)
    db.commit()

    state = grading_tasks.build_grading_state(
        submission,
        assignment,
        grading_tasks.rubric_from_ai_rule(assignment.ai_rule),
        routing={"rule_model_code": "mimo", "rule_prompt": "按实验要求评分"},
    )

    assert state["rule_model_code"] == "mimo"
    assert state["rule_prompt"] == "按实验要求评分"
    assert "structurer_enabled" not in state
    assert "structurer_model_code" not in state
