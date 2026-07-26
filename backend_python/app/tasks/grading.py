"""批改任务的版本幂等边界。"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..agent.graphs.grading import build_grading_graph
from ..agent.subagents import grading, grading_review
from ..agent.tools.content import normalize_submission_content
from ..assistant_database import AssistantSessionLocal
from ..agent.contracts import GradingRubric, RubricCriterion
from ..config import settings
from ..crud import agent_run, agent_session
from ..crud.submission import apply_ai_grading_result
from ..database import SessionLocal
from ..models import AgentRun, AgentSession, Assignment, Submission
from .celery_app import celery_app


def build_grading_idempotency_key(
    submission_id: int,
    submission_count: int,
    rubric_version: str,
) -> str:
    """生成可读且稳定的业务幂等键。"""

    if submission_id <= 0 or submission_count <= 0:
        raise ValueError("submission_id 和 submission_count 必须为正整数")
    version = rubric_version.strip()
    if not version:
        raise ValueError("rubric_version 不能为空")
    return (
        f"grading:submission:{submission_id}:version:{submission_count}:"
        f"rubric:{version}"
    )


def rubric_from_ai_rule(ai_rule: dict) -> GradingRubric:
    """把新旧 AI 规则统一为版本化评分量表。"""

    criteria_data = ai_rule.get("criteria") or []
    if criteria_data:
        criteria = [
            RubricCriterion(
                criterion_id=str(item.get("id") or item.get("criterionId")),
                title=str(item.get("title") or item.get("name")),
                max_score=float(item.get("maxScore", item.get("max_score"))),
                instructions=str(item.get("instructions") or ""),
            )
            for item in criteria_data
        ]
        version = str(
            ai_rule.get("version")
            or ai_rule.get("rubricVersion")
            or "rubric-v1"
        )
        return GradingRubric(version=version, criteria=criteria)

    max_score = float(ai_rule.get("maxScore") or 100)
    fingerprint = hashlib.sha256(
        repr(sorted(ai_rule.items())).encode("utf-8"),
    ).hexdigest()[:12]
    version = str(
        ai_rule.get("version")
        or ai_rule.get("rubricVersion")
        or f"legacy-{fingerprint}"
    )
    return GradingRubric(
        version=version,
        criteria=[RubricCriterion(
            criterion_id="overall",
            title="综合质量",
            max_score=max_score,
            instructions=str(ai_rule.get("prompt") or ""),
        )],
    )


def _session_id_for_key(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:40]
    return f"grading-{digest}"


def enqueue_grading_job(
    business_db: Session,
    run_db: Session,
    *,
    submission: Submission,
    user_id: int,
    actor_role: str,
) -> str | None:
    """创建持久化 Run，并且每个提交版本只投递一次。"""

    assignment = business_db.query(Assignment).filter(
        Assignment.id == submission.assignment_id,
    ).first()
    if not assignment or not assignment.ai_rule:
        return None
    rubric = rubric_from_ai_rule(assignment.ai_rule)
    key = build_grading_idempotency_key(
        submission.id,
        submission.submission_count,
        rubric.version,
    )
    session_id = _session_id_for_key(key)
    session = run_db.query(AgentSession).filter(
        AgentSession.id == session_id,
    ).first()
    if session is None:
        try:
            agent_session.create_session(
                run_db,
                user_id=user_id,
                actor_role=actor_role,
                session_id=session_id,
                title=f"批改任务：{assignment.title}",
            )
        except IntegrityError:
            run_db.rollback()
            session = run_db.query(AgentSession).filter(
                AgentSession.id == session_id,
            ).first()
            if (
                session is None
                or session.user_id != user_id
                or session.actor_role != actor_role
            ):
                raise
    elif session.user_id != user_id or session.actor_role != actor_role:
        raise ValueError("批改任务会话归属冲突")

    existing = (
        run_db.query(AgentRun)
        .filter(
            AgentRun.session_id == session_id,
            AgentRun.user_id == user_id,
            AgentRun.intent == "grading",
            AgentRun.status.in_(["running", "completed"]),
        )
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if existing is not None:
        return existing.id

    deterministic_run_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
    try:
        run = agent_run.create_run(
            run_db,
            session_id=session_id,
            user_id=user_id,
            intent="grading",
            risk_level="medium",
            graph_version="grading-v1",
            run_id=deterministic_run_id,
        )
    except IntegrityError:
        run_db.rollback()
        run = agent_run.get_run(run_db, deterministic_run_id, user_id)
        if run is None:
            raise
        return run.id
    try:
        run_grading_task.delay(
            submission_id=submission.id,
            submission_count=submission.submission_count,
            rubric_version=rubric.version,
            run_id=run.id,
            user_id=user_id,
        )
    except Exception:
        agent_run.fail_run(
            run_db,
            run.id,
            user_id,
            "AGENT_QUEUE_UNAVAILABLE",
        )
        raise
    return run.id


def _run_production_workflow(
    business_db: Session,
    submission: Submission,
    assignment: Assignment,
    rubric: GradingRubric,
) -> dict:
    def normalize_node(_state):
        return {
            "normalized_content": normalize_submission_content(
                rich_text=submission.content or "",
                attachments=submission.attachments or [],
                upload_dir=settings.upload_path,
            ),
        }

    graph = build_grading_graph(
        normalize_node,
        grading.create_node(business_db),
        grading_review.create_node(business_db),
    )
    return graph.invoke({
        "submission_id": submission.id,
        "submission_count": submission.submission_count,
        "rubric": rubric,
    })


def execute_grading_job(
    *,
    submission_id: int,
    submission_count: int,
    rubric_version: str,
    run_id: str,
    user_id: int,
    business_db: Session | None = None,
    run_db: Session | None = None,
    workflow_runner=None,
) -> dict:
    """执行可安全重跑的批改任务并持久化 Step/Artifact。"""

    owns_business_db = business_db is None
    owns_run_db = run_db is None
    biz = business_db or SessionLocal()
    audit = run_db or AssistantSessionLocal()
    try:
        run = agent_run.get_run(audit, run_id, user_id)
        if run is None:
            raise ValueError("批改运行不存在或不属于当前用户")
        if run.status == "cancelled":
            return {"status": "cancelled", "run_id": run_id}
        if run.status == "completed":
            return {"status": "completed", "run_id": run_id}
        if run.status not in {"running", "processing"}:
            return {"status": run.status, "run_id": run_id}
        claimed = (
            audit.query(AgentRun)
            .filter(
                AgentRun.id == run_id,
                AgentRun.user_id == user_id,
                AgentRun.status.in_(["running", "processing"]),
            )
            .update(
                {AgentRun.status: "processing"},
                synchronize_session=False,
            )
        )
        audit.commit()
        if claimed != 1:
            current = agent_run.get_run(audit, run_id, user_id)
            return {
                "status": current.status if current else "missing",
                "run_id": run_id,
            }

        submission = biz.query(Submission).filter(
            Submission.id == submission_id,
        ).first()
        if (
            submission is None
            or submission.submission_count != submission_count
        ):
            agent_run.finalize_run(
                audit,
                run_id,
                user_id,
                final_output="提交版本已变化，旧批改任务未写回。",
                artifacts=[{
                    "artifact_type": "grading_stale",
                    "schema_version": "v1",
                    "payload": {
                        "submission_id": submission_id,
                        "expected_submission_count": submission_count,
                    },
                }],
            )
            return {"status": "stale", "run_id": run_id}

        assignment = biz.query(Assignment).filter(
            Assignment.id == submission.assignment_id,
        ).first()
        if not assignment or not assignment.ai_rule:
            raise ValueError("作业未配置 AI 评分规则")
        rubric = rubric_from_ai_rule(assignment.ai_rule)
        if rubric.version != rubric_version:
            raise ValueError("评分量表版本已变化")

        runner = workflow_runner or _run_production_workflow
        graph_result = runner(biz, submission, assignment, rubric)
        outcome = graph_result["outcome"]
        for node_name in graph_result.get("visited_nodes", []):
            agent_run.append_step(
                audit,
                run_id,
                user_id,
                node_name=node_name,
                status="completed",
            )

        audit.expire_all()
        current_run = agent_run.get_run(audit, run_id, user_id)
        if current_run is None or current_run.status == "cancelled":
            return {"status": "cancelled", "run_id": run_id}

        applied = apply_ai_grading_result(
            biz,
            submission_id=submission_id,
            expected_submission_count=submission_count,
            outcome=outcome,
        )
        if not applied:
            final_output = "提交版本已变化，批改结果未写回。"
            status = "stale"
        else:
            final_output = (
                "批改完成，等待教师人工复核。"
                if outcome.needs_human_review
                else "批改完成。"
            )
            status = "completed"
        agent_run.finalize_run(
            audit,
            run_id,
            user_id,
            final_output=final_output,
            artifacts=[{
                "artifact_type": "grading_outcome",
                "schema_version": outcome.schema_version,
                "payload": outcome.model_dump(mode="json"),
            }],
        )
        return {"status": status, "run_id": run_id}
    except Exception:
        try:
            existing = agent_run.get_run(audit, run_id, user_id)
            if (
                existing is not None
                and existing.status in {"running", "processing"}
            ):
                agent_run.fail_run(
                    audit,
                    run_id,
                    user_id,
                    "AGENT_GRADING_FAILED",
                )
        finally:
            raise
    finally:
        if owns_business_db:
            biz.close()
        if owns_run_db:
            audit.close()


@celery_app.task(
    bind=True,
    name="agent.grading.run",
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_grading_task(
    self,
    *,
    submission_id: int,
    submission_count: int,
    rubric_version: str,
    run_id: str,
    user_id: int,
):
    return execute_grading_job(
        submission_id=submission_id,
        submission_count=submission_count,
        rubric_version=rubric_version,
        run_id=run_id,
        user_id=user_id,
    )


__all__ = [
    "build_grading_idempotency_key",
    "enqueue_grading_job",
    "execute_grading_job",
    "rubric_from_ai_rule",
    "run_grading_task",
]
