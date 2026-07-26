"""审批后的业务写操作执行器；执行前再次校验角色与对象权限。"""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from . import ai_rule as ai_rule_crud
from . import assignment as assignment_crud
from . import correcting as correcting_crud
from . import ai_model as ai_model_crud
from ..models import (
    AgentActionExecution,
    Assignment,
    Class,
    Submission,
    User,
)

_ROLE_ACTIONS = {
    "teacher": {
        "create_assignment_draft",
        "create_ai_rule",
        "submit_teacher_score",
    },
    "superadmin": {
        "create_ai_rule",
        "update_model_config",
    },
}

_AI_RULE_ALLOWED_FIELDS = {
    "name",
    "description",
    "modelType",
    "prompt",
    "status",
    "visibility",
    "tags",
    "maxScore",
}

_GRADEABLE_SUBMISSION_STATUSES = {
    "submitted",
    "ai_reviewed",
    "teacher_reviewed",
}


def _parse_positive_int_id(value, label: str) -> int:
    if type(value) is int:
        parsed = value
    elif isinstance(value, str) and value.isdigit():
        parsed = int(value)
    else:
        raise ValueError(f"{label}格式非法")
    if parsed <= 0:
        raise ValueError(f"{label}格式非法")
    return parsed


def validate_action_permission(
    action_type: str,
    payload: dict,
    actor_user_id: int,
    actor_role: str,
    db: Session | None = None,
) -> None:
    if action_type not in _ROLE_ACTIONS.get(actor_role, set()):
        raise ValueError("当前角色无权审批该操作")
    if action_type == "create_ai_rule":
        unknown_fields = set(payload) - _AI_RULE_ALLOWED_FIELDS
        if unknown_fields:
            raise ValueError("AI 规则载荷包含未授权字段")
    if action_type == "create_assignment_draft" and db is not None:
        raw_class_ids = payload.get("classes", [])
        if not isinstance(raw_class_ids, list):
            raise ValueError("班级列表格式非法")
        try:
            class_ids = [
                _parse_positive_int_id(class_id, "班级 ID")
                for class_id in raw_class_ids
            ]
        except ValueError as exc:
            raise ValueError("班级列表包含非法 ID") from exc
        classes = (
            db.query(Class).filter(Class.id.in_(set(class_ids))).all()
            if class_ids
            else []
        )
        owned_ids = {
            class_.id
            for class_ in classes
            if class_.teacher_id == actor_user_id
        }
        if owned_ids != set(class_ids):
            raise ValueError("班级不存在或不属于当前教师")
    if action_type == "update_model_config":
        changes = payload.get("changes")
        if not payload.get("code") or not isinstance(changes, dict) or not changes:
            raise ValueError("模型配置变更载荷不完整")
        allowed = {"name", "modelName", "baseUrl", "status", "isDefault"}
        sensitive = {
            "apiKey", "api_key", "accessKey", "access_key",
            "secretKey", "secret_key", "password",
        }
        keys = set(changes)
        if keys & sensitive:
            raise ValueError("审批载荷禁止包含敏感凭据")
        if keys - allowed:
            raise ValueError("审批载荷包含未授权模型配置字段")
    if action_type == "submit_teacher_score" and db is not None:
        try:
            submission_id = _parse_positive_int_id(
                payload.get("submissionId"),
                "提交记录 ID",
            )
            score = float(payload["teacherScore"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("提交记录或教师分数格式非法") from exc
        submission = db.query(Submission).filter(
            Submission.id == submission_id,
        ).first()
        assignment = (
            db.query(Assignment).filter(
                Assignment.id == submission.assignment_id,
            ).first()
            if submission
            else None
        )
        if not submission or not assignment or assignment.teacher_id != actor_user_id:
            raise ValueError("无权批改该提交")
        if (
            payload.get("assignmentId") is not None
            and str(payload["assignmentId"]) != str(submission.assignment_id)
        ):
            raise ValueError("载荷作业与提交记录所属作业不一致")
        if (
            payload.get("classId") is not None
            and str(payload["classId"]) != str(submission.class_id)
        ):
            raise ValueError("载荷班级与提交记录所属班级不一致")
        if submission.status not in _GRADEABLE_SUBMISSION_STATUSES:
            raise ValueError("提交记录当前状态不可批改")
        max_score = 100.0
        if assignment.ai_rule and isinstance(assignment.ai_rule, dict):
            try:
                max_score = float(assignment.ai_rule.get("maxScore", 100))
            except (TypeError, ValueError) as exc:
                raise ValueError("作业满分配置非法") from exc
        if (
            not math.isfinite(score)
            or not math.isfinite(max_score)
            or max_score < 0
            or score < 0
            or score > max_score
        ):
            raise ValueError("教师分数必须为有限值且在作业满分范围内")


def execute_approved_business_action(
    db: Session,
    *,
    actor: User,
    action_type: str,
    payload: dict,
    idempotency_key: str,
) -> dict:
    """执行白名单操作；MySQL 幂等账本提供跨库崩溃后的重复执行保护。"""

    validate_action_permission(
        action_type,
        payload,
        actor.id,
        actor.role,
        db,
    )
    ledger = db.query(AgentActionExecution).filter(
        AgentActionExecution.idempotency_key == idempotency_key,
    ).first()
    if ledger is not None:
        if ledger.action_type != action_type:
            raise ValueError("幂等键已被其他操作占用")
        if ledger.status == "completed":
            return ledger.result_json or {}
        raise ValueError("该操作已进入执行流程，请人工核对执行结果")
    ledger = AgentActionExecution(
        idempotency_key=idempotency_key,
        action_type=action_type,
        status="executing",
    )
    db.add(ledger)
    db.commit()
    try:
        result = _execute_business_action(
            db,
            actor=actor,
            action_type=action_type,
            payload=payload,
        )
        ledger = db.query(AgentActionExecution).filter(
            AgentActionExecution.idempotency_key == idempotency_key,
        ).one()
        ledger.status = "completed"
        ledger.result_json = result
        db.commit()
        return result
    except Exception:
        db.rollback()
        ledger = db.query(AgentActionExecution).filter(
            AgentActionExecution.idempotency_key == idempotency_key,
        ).first()
        if ledger is not None and ledger.status == "executing":
            ledger.status = "failed"
            ledger.error_code = "BUSINESS_ACTION_FAILED"
            db.commit()
        raise


def _execute_business_action(
    db: Session,
    *,
    actor: User,
    action_type: str,
    payload: dict,
) -> dict:
    if action_type == "create_assignment_draft":
        data = dict(payload)
        data["status"] = "draft"
        result = assignment_crud.create_assignment(
            db,
            teacher_id=actor.id,
            teacher_name=actor.name,
            data=data,
        )
        return {"success": True, "resource": result}
    if action_type == "create_ai_rule":
        data = {
            key: payload[key]
            for key in _AI_RULE_ALLOWED_FIELDS
            if key in payload
        }
        data["createdBy"] = {"id": str(actor.id), "name": actor.name}
        return ai_rule_crud.create(db, data)
    if action_type == "submit_teacher_score":
        score = float(payload["teacherScore"])
        if score < 0:
            raise ValueError("教师评分不能小于 0")
        return correcting_crud.submit_teacher_review(
            db,
            submission_id=int(payload["submissionId"]),
            teacher_score=score,
            teacher_review_content=str(payload.get("teacherReviewContent", "")),
        )
    if action_type == "update_model_config":
        model = ai_model_crud.update_config(
            db,
            code=str(payload["code"]),
            data=dict(payload["changes"]),
        )
        safe_model = {
            key: model.get(key)
            for key in (
                "code", "name", "provider", "modelName",
                "baseUrl", "status", "isDefault",
            )
            if key in model
        }
        return {"success": True, "resource": safe_model}
    raise ValueError("该操作尚未注册审批后执行器")


__all__ = [
    "execute_approved_business_action",
    "validate_action_permission",
]
