"""Token 用量落库（规划阶段 4.1 验收）。

- 教师运行：带用量的节点更新写 Step.usage_json，finalize 聚合写 Run.usage_json。
- 批改任务：图状态 usage 写 Run.usage_json。
- AiModel.total_usage/total_tokens 原子自增。
"""
from datetime import datetime, timedelta

import pytest

from app.agent.contracts import ReviewResult, SpecialistResponse
from app.agent.service import orchestrate_teacher_run
from app.crud import ai_model as ai_model_crud
from app.crud.agent_session import create_session
from app.models import AgentRun, AgentStep, Assignment, Submission
from app.tasks import grading as grading_tasks


def _usage(prompt: int, completion: int) -> dict:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


class _UsageSpecialists:
    """节点更新带 usage 的教师替身。"""

    def teaching_data(self, state):
        response = SpecialistResponse(
            answer="已找到 2 个班级",
            evidence_refs=["class:7:count"],
        )
        return {
            "candidate_answer": response.answer,
            "evidence_refs": response.evidence_refs,
            "specialist_response": response,
            "usage": _usage(120, 30),
        }

    def teaching_strategy(self, state):
        return {"candidate_answer": "建议加强练习"}

    def final_reviewer(self, state):
        return {
            "review": ReviewResult(approved=True, issues=[]),
            "usage": _usage(40, 10),
        }


def test_teacher_run_persists_step_and_run_usage(assistant_db):
    session = create_session(
        assistant_db, user_id=7, actor_role="teacher", session_id="sessusage0001",
    )

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-usage-001",
        specialists=_UsageSpecialists(),
        assistant_db=assistant_db,
    )

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(
        AgentRun.id == result.run_id,
    ).one()
    # 运行级聚合非空（阶段 4 验收点）
    assert run.usage_json == _usage(160, 40)
    steps = {
        step.node_name: step
        for step in assistant_db.query(AgentStep).filter(
            AgentStep.run_id == run.id,
        )
    }
    assert steps["teacher_data_agent"].usage_json == _usage(120, 30)
    assert steps["final_reviewer_agent"].usage_json == _usage(40, 10)
    # 无模型调用的节点不落用量
    assert not steps["teacher_supervisor"].usage_json


def test_ai_model_counters_increment_atomically(db, ai_model_factory):
    model = ai_model_factory()
    ai_model_crud.increment_usage(db, model_id=model.id, calls=2, tokens=200)
    ai_model_crud.increment_usage(db, model_id=model.id, calls=1, tokens=55)

    db.expire_all()
    assert model.total_usage == 3
    assert model.total_tokens == 255
    assert model.last_used_at is not None


def test_grading_run_persists_usage_and_increments_model(
    db, assistant_db, student, ai_model_factory, monkeypatch,
):
    model = ai_model_factory()
    assignment = Assignment(
        title="用量作业",
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
        grading_tasks.run_grading_task, "delay", lambda **kwargs: None,
    )
    run_id = grading_tasks.enqueue_grading_job(
        db, assistant_db,
        submission=submission, user_id=student.id, actor_role="student",
    )

    from tests.integration.agent.test_grading_jobs import _outcome

    grading_tasks.execute_grading_job(
        submission_id=submission.id,
        submission_count=2,
        rubric_version="rubric-v3",
        run_id=run_id,
        user_id=student.id,
        business_db=db,
        run_db=assistant_db,
        workflow_runner=lambda *_: {
            "outcome": _outcome(),
            "usage": _usage(500, 120),
            "visited_nodes": ["normalize_submission_content", "grading_agent"],
        },
    )

    assistant_db.expire_all()
    run = assistant_db.query(AgentRun).filter(AgentRun.id == run_id).one()
    assert run.usage_json == _usage(500, 120)
    db.expire_all()
    assert model.total_tokens == 620
    assert model.total_usage >= 1
