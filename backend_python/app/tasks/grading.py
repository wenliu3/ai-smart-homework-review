"""批改任务的版本幂等边界。"""
from __future__ import annotations

import hashlib
import logging

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..agent.graphs.grading import build_grading_graph
from ..agent.runtime import BudgetExceeded, grading_run_budget
from ..agent.subagents import grading, grading_review
from ..agent.tools.content import (
    extract_reference_materials,
    normalize_submission_content,
)
from ..assistant_database import AssistantSessionLocal
from ..agent.contracts import (
    AGENT_GRADING_TIMEOUT,
    GradingRubric,
    RubricCriterion,
)
from ..config import settings
from ..crud import agent_run, agent_session
from ..crud.submission import (
    apply_ai_grading_result,
    mark_submission_needs_manual_grading,
)
from ..database import SessionLocal
from ..models import AgentRun, AgentSession, Assignment, Submission
from .celery_app import celery_app

logger = logging.getLogger(__name__)

# 降级转人工时写给教师端的提示（服务端文案，不经模型）
MANUAL_GRADING_NOTE = (
    "⚠️ AI 批改未能生成有效的结构化评分，本次提交需要教师人工批改。"
)


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
        Assignment.alive(),
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
        _record_grading_run_id(business_db, submission, existing.id)
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
        _record_grading_run_id(business_db, submission, run.id)
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
    _record_grading_run_id(business_db, submission, run.id)
    return run.id


def _record_grading_run_id(
    business_db: Session,
    submission: Submission,
    run_id: str,
) -> None:
    """把批改 run 记到提交行：学生轮询进度、教师查产物都由此定位。"""
    if submission.grading_run_id == run_id:
        return
    submission.grading_run_id = run_id
    business_db.commit()


def _record_grading_model_usage(business_db: Session, graph_result: dict) -> None:
    """批改运行的模型用量累加（尽力而为，失败不影响批改结果）。"""
    usage = graph_result.get("usage") or {}
    calls = getattr(
        graph_result.get("runtime_budget"), "model_call_count", 0,
    ) or (1 if usage else 0)
    if not usage and calls <= 0:
        return
    try:
        from ..agent.gateway import model_gateway
        from ..crud import ai_model as ai_model_crud

        config = model_gateway.get_default_config(business_db)
        ai_model_crud.increment_usage(
            business_db,
            model_id=config.id,
            calls=calls,
            tokens=int(usage.get("total_tokens", 0)),
        )
    except Exception:
        logger.warning("批改模型用量统计写入失败", exc_info=True)


def build_grading_state(
    submission: Submission,
    assignment: Assignment,
    rubric: GradingRubric,
    upload_dir=None,
) -> dict:
    """构造批改图初始状态：作业要求 + 参考资料 + 预算（规划 3B.1 / 3B.2）。"""
    base = upload_dir if upload_dir is not None else settings.upload_path
    return {
        "submission_id": submission.id,
        "submission_count": submission.submission_count,
        "rubric": rubric,
        "assignment_description": (assignment.description or "").strip(),
        "reference_materials": extract_reference_materials(
            assignment.attachments or [],
            base,
        ),
        "runtime_budget": grading_run_budget(),
    }


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
    return graph.invoke(build_grading_state(submission, assignment, rubric))


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
            Assignment.alive(),
            Assignment.id == submission.assignment_id,
        ).first()
        if not assignment or not assignment.ai_rule:
            raise ValueError("作业未配置 AI 评分规则")
        rubric = rubric_from_ai_rule(assignment.ai_rule)
        if rubric.version != rubric_version:
            raise ValueError("评分量表版本已变化")

        runner = workflow_runner or _run_production_workflow
        try:
            graph_result = runner(biz, submission, assignment, rubric)
        except BudgetExceeded as exc:
            # 预算耗尽与结构化失败同等处理：转人工，不丢结果不炸任务
            graph_result = {
                "grading_failure": {
                    "stage": "budget",
                    "error": str(exc),
                    "raw_response": "",
                },
                "visited_nodes": [],
            }
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

        failure = graph_result.get("grading_failure")
        if failure:
            # 降级转人工：原始草案留证到 Artifact，教师端拿到明确提示；
            # run 记为 completed——这是受控降级，不是任务失败
            mark_submission_needs_manual_grading(
                biz,
                submission_id=submission_id,
                expected_submission_count=submission_count,
                note=MANUAL_GRADING_NOTE,
            )
            agent_run.finalize_run(
                audit,
                run_id,
                user_id,
                final_output="AI 批改未通过结构化校验，已转教师人工批改。",
                artifacts=[{
                    "artifact_type": "grading_raw_draft",
                    "schema_version": "v1",
                    "payload": failure,
                }],
                usage=graph_result.get("usage") or None,
            )
            _record_grading_model_usage(biz, graph_result)
            return {"status": "completed", "run_id": run_id}

        outcome = graph_result["outcome"]
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
            usage=graph_result.get("usage") or None,
        )
        _record_grading_model_usage(biz, graph_result)
        return {"status": status, "run_id": run_id}
    except SoftTimeLimitExceeded:
        # Celery 软超时：预算应先于它触发，走到这里说明 worker 卡死，
        # 用独立错误码标记以便与普通失败区分（运营排查队列拥塞）
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
                    AGENT_GRADING_TIMEOUT,
                )
        finally:
            raise
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
    # 与 grading_run_budget 的 120s 对齐：预算超时优先走结构化降级，
    # soft_time_limit 是 worker 卡死时的最后兜底；hard limit 再留 30s 清理余量
    soft_time_limit=120,
    time_limit=150,
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
