"""PostgreSQL Agent 运行、步骤与产物 CRUD。

运行（AgentRun）记录一次图执行的所有者、意图、状态、模型用量、最终输出和
错误码；步骤（AgentStep）记录节点序号、状态、证据引用和模型用量；产物
（AgentArtifact）保存版本化的 JSON 结构化结果。

关键约束：
- 所有写操作必须先校验运行归属当前用户（防止越权写入他人运行）。
- `finalize_run` 在同一 PostgreSQL 事务中提交最终消息、Artifact 和
  `run.completed` 状态，任一失败整体回滚，不留半状态。
- 图状态不得保存 ORM 对象；本模块只在持久化边界构造 ORM 实例。
"""
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AgentArtifact, AgentMessage, AgentRun, AgentSession, AgentStep

logger = logging.getLogger(__name__)

# 批改 run 陈旧的判定阈值（秒）：processing 超过该时长仍未结束视为僵尸 run
# （worker 已被硬超时 kill 或队列拥塞），读取时收口为 failed/AGENT_GRADING_TIMEOUT。
GRADING_STALE_SECONDS = 180


# ========== Run 生命周期 ==========

def create_run(
    db: Session,
    session_id: str,
    user_id: int,
    intent: str,
    risk_level: str = "low",
    graph_version: str = "teacher-v1",
    run_id: str | None = None,
) -> AgentRun:
    """启动一次运行。会话必须属于当前用户且仍活跃。"""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == user_id,
        AgentSession.status == "active",
    ).first()
    if not session:
        raise ValueError("会话不存在或不属于当前用户")
    run = AgentRun(
        id=run_id or uuid4().hex,
        session_id=session_id,
        user_id=user_id,
        intent=intent,
        risk_level=risk_level,
        graph_version=graph_version,
        status="running",
        started_at=datetime.now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _load_owned_run(
    db: Session,
    run_id: str,
    user_id: int,
    *,
    for_update: bool = False,
) -> AgentRun:
    """加载运行并校验归属；不存在或不属于当前用户则抛 ValueError。"""
    query = db.query(AgentRun).filter(
        AgentRun.id == run_id,
        AgentRun.user_id == user_id,
    )
    if for_update:
        query = query.with_for_update()
    run = query.first()
    if not run:
        raise ValueError("运行不存在或不属于当前用户")
    return run


def get_run(db: Session, run_id: str, user_id: int) -> AgentRun | None:
    """读取运行（含 steps/artifacts 关系）。跨用户返回 None。"""
    return (
        db.query(AgentRun)
        .filter(AgentRun.id == run_id, AgentRun.user_id == user_id)
        .first()
    )


def update_run_route(
    db: Session,
    run_id: str,
    user_id: int,
    intent: str,
    risk_level: str,
) -> AgentRun:
    """路由节点完成后回填服务端判定的意图和风险等级。"""
    run = _load_owned_run(db, run_id, user_id)
    if run.status != "running":
        raise ValueError(f"只有 running 状态可更新路由，当前状态为 {run.status}")
    run.intent = intent
    run.risk_level = risk_level
    db.commit()
    db.refresh(run)
    return run


def complete_run(db: Session, run_id: str, user_id: int, final_output: str) -> None:
    """简单完成（无 Artifact / 消息）。需要原子事务时使用 finalize_run。"""
    run = _load_owned_run(db, run_id, user_id, for_update=True)
    if run.status not in {"running", "processing"}:
        return
    run.status = "completed"
    run.final_output = final_output
    run.finished_at = datetime.now()
    db.commit()


def fail_run(db: Session, run_id: str, user_id: int, error_code: str) -> None:
    """标记运行失败并写入稳定错误码。"""
    run = _load_owned_run(db, run_id, user_id, for_update=True)
    if run.status not in {"running", "processing"}:
        return
    run.status = "failed"
    run.error_code = error_code
    run.finished_at = datetime.now()
    db.commit()


def cancel_run(db: Session, run_id: str, user_id: int) -> None:
    """标记运行被取消（用户主动取消或超时中止）。"""
    run = _load_owned_run(db, run_id, user_id, for_update=True)
    if run.status not in {"running", "processing"}:
        return
    run.status = "cancelled"
    run.finished_at = datetime.now()
    db.commit()


def finalize_stale_grading_runs(
    db: Session,
    *,
    user_id: int | None = None,
    max_age_seconds: int = GRADING_STALE_SECONDS,
) -> int:
    """收口历史陈旧僵尸批改 run：processing 且超阈值未结束 → failed/AGENT_GRADING_TIMEOUT。

    - 幂等：只动 `intent=="grading"` 且 `status=="processing"` 的目标行，
      终态（completed/failed/cancelled）与 running 永不被覆盖；
    - 时间边界用应用时钟 `datetime.now()`（与 create_run 写入的 started_at 同源），
      批量 UPDATE 直接落库；传 `user_id` 时再限定归属，防止收口他人 run；
    - 返回收口行数。调用方（路由层）负责兜底异常，本函数不向调用方抛破坏性错误。
    """
    from ..agent.contracts import AGENT_GRADING_TIMEOUT

    cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
    query = db.query(AgentRun).filter(
        AgentRun.intent == "grading",
        AgentRun.status == "processing",
        AgentRun.started_at < cutoff,
    )
    if user_id is not None:
        query = query.filter(AgentRun.user_id == user_id)
    closed = query.update(
        {
            AgentRun.status: "failed",
            AgentRun.error_code: AGENT_GRADING_TIMEOUT,
            AgentRun.finished_at: datetime.now(),
        },
        synchronize_session=False,
    )
    # 无目标行时不提交，避免读取路径每次查询都开启一个写事务
    if closed:
        db.commit()
    return closed


def finalize_run(
    db: Session,
    run_id: str,
    user_id: int,
    final_output: str,
    assistant_message: str | None = None,
    artifacts: list[dict] | None = None,
    usage: dict | None = None,
) -> AgentRun:
    """原子完成运行：同一 PostgreSQL 事务提交最终消息、Artifact 和 run.completed。

    - 任一写入失败整体回滚，运行保持 `running` 状态，不留半状态。
    - `artifacts` 列表每项形如
      `{"artifact_type": "...", "schema_version": "...", "payload": {...}}`。
    - `assistant_message` 提供时写入 agent_messages 并关联本次 run_id。
    - `usage` 提供且非空时写入 run.usage_json（规划 4.1）。
    """
    run = _load_owned_run(db, run_id, user_id, for_update=True)
    if run.status not in {"running", "processing"}:
        raise ValueError(f"只有活动状态可完成，当前状态为 {run.status}")
    try:
        run.status = "completed"
        run.final_output = final_output
        run.finished_at = datetime.now()
        if usage:
            run.usage_json = usage

        if assistant_message is not None:
            db.add(AgentMessage(
                session_id=run.session_id,
                run_id=run.id,
                role="assistant",
                content=assistant_message,
                content_type="markdown",
                metadata_json={},
            ))

        for art in artifacts or []:
            db.add(AgentArtifact(
                run_id=run.id,
                artifact_type=art["artifact_type"],
                schema_version=art["schema_version"],
                payload_json=art["payload"],
            ))

        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        logger.exception("finalize_run 失败，已回滚 run_id=%s", run_id)
        raise


# ========== Step ==========

def append_step(
    db: Session,
    run_id: str,
    user_id: int,
    node_name: str,
    status: str,
    output: dict | None = None,
    evidence_refs: list[str] | None = None,
    usage: dict | None = None,
    error_code: str | None = None,
    duration_ms: int = 0,
) -> AgentStep:
    """追加一个 Step，sequence 自增。跨用户运行拒绝写入。"""
    _load_owned_run(db, run_id, user_id)
    last_sequence = (
        db.query(func.max(AgentStep.sequence))
        .filter(AgentStep.run_id == run_id)
        .scalar()
        or 0
    )
    step = AgentStep(
        run_id=run_id,
        sequence=last_sequence + 1,
        node_name=node_name,
        status=status,
        output_json=output or {},
        evidence_refs=evidence_refs or [],
        usage_json=usage or {},
        error_code=error_code,
        duration_ms=duration_ms,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def start_step(
    db: Session,
    run_id: str,
    user_id: int,
    node_name: str,
) -> AgentStep:
    """节点开始执行时先落一条 running Step（规划 4.4 生命周期）。"""
    return append_step(
        db,
        run_id=run_id,
        user_id=user_id,
        node_name=node_name,
        status="running",
    )


def finish_step(
    db: Session,
    step_id: int,
    user_id: int,
    *,
    status: str,
    output: dict | None = None,
    evidence_refs: list[str] | None = None,
    usage: dict | None = None,
    error_code: str | None = None,
    duration_ms: int = 0,
) -> AgentStep | None:
    """原地把 running Step 收口为 completed/failed/cancelled。跨用户返回 None。"""
    step = (
        db.query(AgentStep)
        .join(AgentRun, AgentRun.id == AgentStep.run_id)
        .filter(AgentStep.id == step_id, AgentRun.user_id == user_id)
        .first()
    )
    if step is None:
        return None
    step.status = status
    if output is not None:
        step.output_json = output
    if evidence_refs is not None:
        step.evidence_refs = evidence_refs
    if usage:
        step.usage_json = usage
    step.error_code = error_code
    step.duration_ms = duration_ms
    db.commit()
    db.refresh(step)
    return step


def list_steps(db: Session, run_id: str, user_id: int) -> list[AgentStep]:
    """按 sequence 正序返回全部 Step。跨用户返回空。"""
    if not get_run(db, run_id, user_id):
        return []
    return (
        db.query(AgentStep)
        .filter(AgentStep.run_id == run_id)
        .order_by(AgentStep.sequence.asc())
        .all()
    )


# ========== Artifact ==========

def append_artifact(
    db: Session,
    run_id: str,
    user_id: int,
    artifact_type: str,
    schema_version: str,
    payload: dict,
) -> AgentArtifact:
    """追加一个版本化 Artifact。跨用户运行拒绝写入。"""
    _load_owned_run(db, run_id, user_id)
    artifact = AgentArtifact(
        run_id=run_id,
        artifact_type=artifact_type,
        schema_version=schema_version,
        payload_json=payload,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def list_artifacts(db: Session, run_id: str, user_id: int) -> list[AgentArtifact]:
    """返回运行的全部 Artifact。跨用户返回空。"""
    if not get_run(db, run_id, user_id):
        return []
    return list_artifacts_unscoped(db, run_id)


def get_run_unscoped(db: Session, run_id: str) -> AgentRun | None:
    """不做归属校验的运行读取。

    仅供受控正文访问端点（superadmin + 授权理由 + 审计日志）调用；
    面向普通请求的路径必须走带 user_id 的 get_run。
    """
    return db.query(AgentRun).filter(AgentRun.id == run_id).first()


def list_artifacts_unscoped(db: Session, run_id: str) -> list[AgentArtifact]:
    """不做归属校验的 Artifact 读取。

    仅供路由层在完成跨库授权（如任课教师经 submission → assignment →
    teacher 链路校验）之后调用；任何直接面向请求参数的路径都必须走
    带 user_id 的 list_artifacts。
    """
    return (
        db.query(AgentArtifact)
        .filter(AgentArtifact.run_id == run_id)
        .order_by(AgentArtifact.id.asc())
        .all()
    )
