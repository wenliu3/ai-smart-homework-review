"""批改任务的版本幂等边界。

批改采用单 Agent 结构化直接路径（LangGraph 图）：规范化提交内容 →
主批改（模型按提示词输出固定 JSON，正则提取 + pydantic 严格校验 +
量表维度一一对应）→ 确定性决策 → 总分由后端汇总写回 submission。

切换背景（2026-08）：整条链路统一 DeepSeek 多模态模型
（deepseek-v4-flash-vision-exp）。此前回退到 7/15 版「直接调用 + 正则提取
总分」的两大原因已消除：mimo 对 tool_choice 不稳定（不再混用供应商）；
V4 thinking 与结构化冲突（gateway 经 extra_body 显式关闭 thinking）。
本路径最终形态本就不依赖 tool_choice 强制结构化——提示词要求 JSON +
从 AIMessage 文本提取 + 校验兜底，对模型宽容度最高。

保留的既有基础设施：
- Celery 异步任务（run_grading_task / GradingTask 硬超时收口）；
- 提交版本幂等（enqueue_grading_job / build_grading_idempotency_key）；
- 受控失败 GradingRoutingError / AGENT_RULE_MODEL_NOT_CONFIGURED
  （作业未配置规则模型 modelType 时在模型调用前受控失败）；
- finalize_run 写 run 终态与 Artifact（grading_outcome / grading_raw_draft）；
- 结构化校验失败/预算耗尽 → 降级转人工（mark_submission_needs_manual_grading），
  模型原始输出留证 Artifact 供排查。
"""
from __future__ import annotations

import hashlib
import logging

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..agent.contracts import (
    AGENT_GRADING_TIMEOUT,
    AGENT_RULE_MODEL_NOT_CONFIGURED,
    GradingRubric,
    RubricCriterion,
)
from ..agent.graphs.grading import build_grading_graph
from ..agent.runtime import BudgetExceeded, grading_run_budget
from ..agent.subagents import grading
from ..agent.tools.content import (
    extract_reference_materials,
    normalize_submission_content,
)
from ..assistant_database import AssistantSessionLocal
from ..config import settings
from ..crud import agent_run, agent_session
from ..crud import ai_model as ai_model_crud
from ..crud.submission import (
    apply_ai_grading_result,
    mark_submission_needs_manual_grading,
)
from ..database import SessionLocal
from ..models import (
    AgentRun,
    AgentSession,
    AiModel,
    Assignment,
    Submission,
)
from .celery_app import celery_app
from .grading_request import GradingTask

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


class GradingRoutingError(Exception):
    """任务层受控失败：批改运行配置无效，需以稳定错误码标记 run。

    覆盖「作业未配置规则模型」配置错误；
    code 为 contracts 里的稳定错误码（如 AGENT_RULE_MODEL_NOT_CONFIGURED），
    由 execute_grading_job 的 except 分支写到 run.error_code。
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _grading_routing_config(business_db: Session, assignment: Assignment) -> dict:
    """构造批改链路的显式运行配置：规则模型 code。

    规则模型 code 只来自作业快照 ai_rule.modelType，**绝不回退默认模型**；
    缺少时抛 GradingRoutingError（稳定错误码 AGENT_RULE_MODEL_NOT_CONFIGURED）。
    """
    ai_rule = assignment.ai_rule or {}
    rule_model_code = str(ai_rule.get("modelType") or "").strip()
    if not rule_model_code:
        raise GradingRoutingError(
            AGENT_RULE_MODEL_NOT_CONFIGURED,
            "作业 AI 规则未配置规则模型（modelType），无法发起批改",
        )
    return {
        "rule_model_code": rule_model_code,
        "rule_prompt": str(ai_rule.get("prompt") or "").strip(),
    }


def _record_grading_model_usage(business_db: Session, graph_result: dict) -> None:
    """批改运行的模型用量按实际 model code 分别累计（尽力而为，失败不影响批改结果）。

    图状态 model_usage 形如 {code: {"calls": N, "total_tokens": T}}，逐项按 code
    查模型 id 后原子自增；找不到对应模型时跳过该项并记 warning，绝不回退默认
    模型、绝不阻塞批改结果。
    """
    model_usage = graph_result.get("model_usage") or {}
    if not model_usage:
        return
    for code, stats in model_usage.items():
        try:
            model = business_db.query(AiModel).filter(
                AiModel.code == code,
            ).first()
            if model is None:
                logger.warning(
                    "批改用量引用的模型 code 不存在，跳过累计: %s",
                    code,
                )
                continue
            ai_model_crud.increment_usage(
                business_db,
                model_id=model.id,
                calls=int(stats.get("calls", 0)),
                tokens=int(stats.get("total_tokens", 0)),
            )
        except Exception:
            logger.warning("批改模型用量统计写入失败 code=%s", code, exc_info=True)
            # increment_usage 内部 commit：失败会把共享会话置于 aborted 态，
            # 不回滚则后续模型的用量全部静默丢失。这里恢复会话，继续累计其他 code。
            business_db.rollback()


def build_grading_state(
    submission: Submission,
    assignment: Assignment,
    rubric: GradingRubric,
    upload_dir=None,
    routing: dict | None = None,
) -> dict:
    """构造批改图初始状态：作业要求 + 参考资料 + 预算 + 规则模型路由。

    routing 由任务层（_grading_routing_config）注入，包含 rule_model_code /
    rule_prompt。未提供时（无 db 上下文的单元测试）保守取 ai_rule 里的规则
    模型与规则文本，保证现有用例不因缺字段而崩。
    """
    base = upload_dir if upload_dir is not None else settings.upload_path
    if routing is None:
        ai_rule = assignment.ai_rule or {}
        routing = {
            "rule_model_code": str(ai_rule.get("modelType") or "").strip(),
            "rule_prompt": str(ai_rule.get("prompt") or "").strip(),
        }
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
        "rule_model_code": routing["rule_model_code"],
        "rule_prompt": routing["rule_prompt"],
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

    # 单 Agent 批改：规则模型（ai_rule.modelType）一次直接结构化出分。
    routing = _grading_routing_config(business_db, assignment)
    state = build_grading_state(
        submission,
        assignment,
        rubric,
        routing=routing,
    )
    graph = build_grading_graph(
        normalize_node,
        grading.create_node(business_db),
    )
    return graph.invoke(state)


def _fail_run_with_code(
    audit: Session,
    run_id: str,
    user_id: int,
    code: str,
) -> None:
    """把仍在 running/processing 的批改 run 标记为 failed 并写入稳定错误码。

    execute_grading_job 的受控失败分支共用；仅当前状态可失败时才落库，
    终态（completed/cancelled/failed）保持不变。调用方用
    `try: _fail_run_with_code(...) finally: raise` 保证原异常继续上抛。
    """
    existing = agent_run.get_run(audit, run_id, user_id)
    if (
        existing is not None
        and existing.status in {"running", "processing"}
    ):
        agent_run.fail_run(audit, run_id, user_id, code)


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
        artifacts = [{
            "artifact_type": "grading_outcome",
            "schema_version": outcome.schema_version,
            "payload": outcome.model_dump(mode="json"),
        }]
        agent_run.finalize_run(
            audit,
            run_id,
            user_id,
            final_output=final_output,
            artifacts=artifacts,
            usage=graph_result.get("usage") or None,
        )
        _record_grading_model_usage(biz, graph_result)
        return {"status": status, "run_id": run_id}
    except GradingRoutingError as exc:
        # 运行配置无效（缺规则模型 modelType）：
        # 模型调用前受控失败，用独立稳定错误码标记 run，不吞成 AGENT_GRADING_FAILED。
        try:
            _fail_run_with_code(audit, run_id, user_id, exc.code)
        finally:
            raise
    except SoftTimeLimitExceeded:
        # Celery 软超时：预算应先于它触发，走到这里说明 worker 卡死，
        # 用独立错误码标记以便与普通失败区分（运营排查队列拥塞）
        try:
            _fail_run_with_code(audit, run_id, user_id, AGENT_GRADING_TIMEOUT)
        finally:
            raise
    except Exception:
        try:
            _fail_run_with_code(audit, run_id, user_id, "AGENT_GRADING_FAILED")
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
    # 单次模型调用超时由网关 GRADING_LLM_TIMEOUT(60s) 兜底；
    # 批改预算 grading_run_budget(120s) 先于软超时触发结构化降级，
    # soft_time_limit 是 worker 卡死时的最后兜底；hard limit 再留 30s 清理余量
    soft_time_limit=120,
    time_limit=150,
    # 父进程硬超时（time_limit）时，Request.on_timeout 钩子负责把 run 收口
    # 为 failed/AGENT_GRADING_TIMEOUT（子进程已被 kill，无法自行收口）
    # 承重不变量：crud.agent_run.GRADING_STALE_SECONDS(180s) 必须大于本任务的
    # time_limit(150s)，否则读取时的僵尸收口会先于父进程硬超时，把仍在跑的
    # run 误标为失败。改任一侧时必须同步核对另一侧。
    base=GradingTask,
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
    "GradingRoutingError",
    "build_grading_idempotency_key",
    "build_grading_state",
    "enqueue_grading_job",
    "execute_grading_job",
    "rubric_from_ai_rule",
    "run_grading_task",
]
