"""PostgreSQL ActionDraft 审批与幂等协调。"""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..agent.contracts import ActionDraft
from ..agent.tools.approval import calculate_payload_hash
from ..models import AgentApproval

logger = logging.getLogger(__name__)

# 命中这些终态的幂等记录时允许归档旧键、重新发起审批
_REISSUABLE_STATUSES = {"rejected", "expired", "failed"}


def _archived_idempotency_key(existing: AgentApproval) -> str:
    """终态记录的幂等键归档值：原键前缀 + superseded 标记 + 旧记录 id 前缀。

    列宽 64：36 + 12 + 16 = 64，既保留审计可溯性又不与新键冲突。
    """
    return f"{existing.idempotency_key[:36]}:superseded:{existing.id[:16]}"


def _get_by_idempotency_key(db: Session, idempotency_key: str) -> AgentApproval | None:
    return db.query(AgentApproval).filter(
        AgentApproval.idempotency_key == idempotency_key,
    ).first()


def create_approval(
    db: Session,
    *,
    draft: ActionDraft,
    requester_user_id: int,
    requester_role: str,
    run_id: str | None = None,
) -> AgentApproval:
    existing = _get_by_idempotency_key(db, draft.idempotency_key)
    if existing is not None:
        if (
            existing.requester_user_id != requester_user_id
            or existing.payload_hash != draft.payload_hash
        ):
            raise ValueError("幂等键已被其他草案占用")
        reissuable = (
            existing.status in _REISSUABLE_STATUSES
            or (existing.status == "pending" and existing.expires_at <= datetime.now())
        )
        if not reissuable:
            return existing
        # 终态/已过期记录：归档旧键释放唯一约束（保留历史审计），再插入新的 pending 记录
        if existing.status == "pending":
            existing.status = "expired"
        existing.idempotency_key = _archived_idempotency_key(existing)
        db.commit()
    approval = AgentApproval(
        id=uuid4().hex,
        run_id=run_id,
        requester_user_id=requester_user_id,
        requester_role=requester_role,
        action_type=draft.action_type.value,
        target_type=draft.target_type,
        target_id=draft.target_id,
        payload_json=draft.parameters,
        payload_hash=draft.payload_hash,
        idempotency_key=draft.idempotency_key,
        summary=draft.summary,
        risk_level=draft.risk_level.value,
        status="pending",
        expires_at=draft.expires_at,
    )
    db.add(approval)
    try:
        db.commit()
    except IntegrityError:
        # 并发竞态：「先查后插」撞唯一约束时回滚重查，返回并发方已插入的记录
        db.rollback()
        concurrent = _get_by_idempotency_key(db, draft.idempotency_key)
        if (
            concurrent is None
            or concurrent.requester_user_id != requester_user_id
            or concurrent.payload_hash != draft.payload_hash
        ):
            raise ValueError("幂等键已被其他草案占用")
        return concurrent
    db.refresh(approval)
    return approval


def get_owned_approval(
    db: Session,
    approval_id: str,
    user_id: int,
) -> AgentApproval | None:
    return db.query(AgentApproval).filter(
        AgentApproval.id == approval_id,
        AgentApproval.requester_user_id == user_id,
    ).first()


def list_owned_approvals(
    db: Session,
    user_id: int,
    status: str | None = None,
) -> list[AgentApproval]:
    query = db.query(AgentApproval).filter(
        AgentApproval.requester_user_id == user_id,
    )
    if status:
        query = query.filter(AgentApproval.status == status)
    return query.order_by(AgentApproval.created_at.desc()).all()


def _authorize_actor(
    approval: AgentApproval,
    actor_user_id: int,
    actor_role: str,
) -> None:
    if (
        approval.requester_user_id != actor_user_id
        or approval.requester_role != actor_role
    ):
        raise ValueError("审批人与草案授权用户不匹配")


def _validate_target_metadata(approval: AgentApproval, payload: dict) -> None:
    target_specs = {
        "create_assignment_draft": ("assignment", None),
        "create_ai_rule": ("ai_rule", None),
        "submit_teacher_score": ("submission", "submissionId"),
        "update_model_config": ("ai_model", "code"),
        "publish_assignment": ("assignment", "assignmentId"),
        "update_assignment": ("assignment", "assignmentId"),
        "delete_assignment": ("assignment", "assignmentId"),
    }
    expected = target_specs.get(approval.action_type)
    if expected is None:
        return
    expected_type, payload_key = expected
    if approval.target_type != expected_type:
        raise ValueError("审批目标类型与操作不一致")
    if payload_key is not None:
        if approval.target_id is None:
            raise ValueError("审批目标 ID 不能为空")
        payload_target_id = payload.get(payload_key)
        if payload_target_id is None or str(payload_target_id) != approval.target_id:
            raise ValueError("审批目标与执行载荷对象不一致")


def approve_and_execute(
    db: Session,
    *,
    approval_id: str,
    actor_user_id: int,
    actor_role: str,
    payload: dict,
    executor,
    permission_checker=None,
) -> dict:
    approval = db.query(AgentApproval).filter(
        AgentApproval.id == approval_id,
    ).with_for_update().first()
    if approval is None:
        raise ValueError("审批记录不存在")
    _authorize_actor(approval, actor_user_id, actor_role)
    if approval.status == "executed":
        return approval.result_json or {}
    if approval.status != "pending":
        raise ValueError(f"审批状态为 {approval.status}，不能执行")
    if approval.expires_at <= datetime.now():
        approval.status = "expired"
        db.commit()
        raise ValueError("审批已过期")
    current_hash = calculate_payload_hash(
        approval.action_type,
        approval.target_type,
        approval.target_id,
        payload,
    )
    if current_hash != approval.payload_hash or payload != approval.payload_json:
        raise ValueError("执行载荷与审批载荷不一致")
    _validate_target_metadata(approval, payload)
    if permission_checker is not None:
        permission_checker(approval.action_type, payload, actor_user_id, actor_role)

    approval.status = "approved"
    approval.approver_user_id = actor_user_id
    approval.approved_at = datetime.now()
    try:
        result = executor(
            approval.action_type,
            payload,
            approval.idempotency_key,
        )
    except Exception:
        db.rollback()
        approval = db.query(AgentApproval).filter(
            AgentApproval.id == approval_id,
        ).one()
        approval.status = "failed"
        approval.error_code = "ACTION_EXECUTION_FAILED"
        db.commit()
        raise
    approval.status = "executed"
    approval.executed_at = datetime.now()
    approval.result_json = result
    try:
        db.commit()
    except Exception:
        # 业务动作已在 MySQL 执行成功，PG 提交失败会留下无法对账的 pending：
        # 重试一次；仍失败则用新会话补写 executed 状态；最终失败记 critical 待人工对账
        db.rollback()
        executed_values = {
            "status": "executed",
            "approver_user_id": actor_user_id,
            "approved_at": datetime.now(),
            "executed_at": datetime.now(),
            "result_json": result,
        }
        try:
            db.query(AgentApproval).filter(
                AgentApproval.id == approval_id,
            ).update(executed_values, synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
            try:
                from ..assistant_database import AssistantSessionLocal
                with AssistantSessionLocal() as repair_db:
                    repair_db.query(AgentApproval).filter(
                        AgentApproval.id == approval_id,
                    ).update(executed_values, synchronize_session=False)
                    repair_db.commit()
            except Exception:
                logger.critical(
                    "审批 %s 的业务动作已执行成功，但 executed 状态写入 PG 失败，"
                    "需人工对账（幂等键 %s）",
                    approval_id,
                    approval.idempotency_key,
                )
    return result


def reject_approval(
    db: Session,
    *,
    approval_id: str,
    actor_user_id: int,
    actor_role: str,
    reason: str,
) -> AgentApproval:
    approval = db.query(AgentApproval).filter(
        AgentApproval.id == approval_id,
    ).with_for_update().first()
    if approval is None:
        raise ValueError("审批记录不存在")
    _authorize_actor(approval, actor_user_id, actor_role)
    if approval.status != "pending":
        raise ValueError(f"审批状态为 {approval.status}，不能拒绝")
    approval.status = "rejected"
    approval.rejected_at = datetime.now()
    approval.rejection_reason = reason
    db.commit()
    db.refresh(approval)
    return approval


__all__ = [
    "approve_and_execute",
    "create_approval",
    "get_owned_approval",
    "list_owned_approvals",
    "reject_approval",
]
