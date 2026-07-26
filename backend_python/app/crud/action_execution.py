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
        "publish_assignment",
        "update_assignment",
        "delete_assignment",
    },
    "superadmin": {
        "create_ai_rule",
        "update_model_config",
    },
}

# 作业生命周期动作：均以 assignmentId 定位对象，共用归属与存在性复验
_ASSIGNMENT_ACTIONS = frozenset({
    "publish_assignment",
    "update_assignment",
    "delete_assignment",
})

# 审批载荷中由服务端注入的保留键：参与哈希复验，但绝不进入业务写路径。
# beforeSnapshot 是创建草案时冻结的旧值快照（决策 D2），仅供审批界面做字段级 diff。
_ACTION_RESERVED_KEYS = frozenset({"assignmentId", "beforeSnapshot"})

# 作业可被 Agent 提案修改的字段（对齐 schemas/assignment.py:AssignmentUpdate）。
# 刻意排除 aiRule（改评分量表会让已有 AI 评分失效）与 attachments
# （引用的是 Agent 无法校验的已上传文件），这两项仍只能在教师页面手工修改。
_ASSIGNMENT_UPDATE_ALLOWED_FIELDS = {
    "title",
    "description",
    "classes",
    "startDate",
    "endDate",
    "allowAttachments",
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


def _assert_owned_classes(db: Session, raw_class_ids, actor_user_id: int) -> None:
    """班级列表必须全部存在且属于当前教师。"""
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


def _validate_assignment_action(
    action_type: str,
    payload: dict,
    actor_user_id: int,
    db: Session,
) -> None:
    """作业生命周期动作的归属、状态机与字段白名单复验。

    存在性/归属在此拦截，避免落到 crud 层抛 NotFoundException 变成 500。
    """
    allowed_keys = set(_ACTION_RESERVED_KEYS)
    if action_type == "update_assignment":
        allowed_keys.add("changes")
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ValueError("作业操作载荷包含未授权字段")

    assignment_id = _parse_positive_int_id(payload.get("assignmentId"), "作业 ID")
    assignment = db.query(Assignment).filter(
        Assignment.alive(),
        Assignment.id == assignment_id,
    ).first()
    if assignment is None or assignment.teacher_id != actor_user_id:
        raise ValueError("作业不存在或不属于当前教师")

    if action_type == "publish_assignment":
        if assignment.status != "draft":
            raise ValueError("作业当前状态不可发布")
        if not assignment.classes:
            raise ValueError("作业未关联班级，不能发布")

    if action_type == "update_assignment":
        changes = payload.get("changes")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("作业更新变更内容不能为空")
        unknown_fields = set(changes) - _ASSIGNMENT_UPDATE_ALLOWED_FIELDS
        if unknown_fields:
            raise ValueError("作业更新载荷包含未授权字段")
        if "classes" in changes:
            _assert_owned_classes(db, changes["classes"], actor_user_id)


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
        _assert_owned_classes(db, payload.get("classes", []), actor_user_id)
    if action_type in _ASSIGNMENT_ACTIONS and db is not None:
        _validate_assignment_action(action_type, payload, actor_user_id, db)
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
                Assignment.alive(),
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

    # 角色白名单不依赖对象状态，任何路径（含重放）都必须先过。
    if action_type not in _ROLE_ACTIONS.get(actor.role, set()):
        raise ValueError("当前角色无权审批该操作")
    ledger = db.query(AgentActionExecution).filter(
        AgentActionExecution.idempotency_key == idempotency_key,
    ).first()
    if ledger is not None:
        if ledger.action_type != action_type:
            raise ValueError("幂等键已被其他操作占用")
        if ledger.status == "completed":
            return ledger.result_json or {}
        raise ValueError("该操作已进入执行流程，请人工核对执行结果")
    # 对象级校验必须在账本命中之后：状态迁移类动作（发布/删除）重放时，
    # 首次执行造成的状态变化会让前置条件不再成立，先校验会把合法重放误拒。
    validate_action_permission(
        action_type,
        payload,
        actor.id,
        actor.role,
        db,
    )
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
            actor_user_id=actor.id,
        )
    if action_type in _ASSIGNMENT_ACTIONS:
        assignment_id = _parse_positive_int_id(payload.get("assignmentId"), "作业 ID")
        if action_type == "publish_assignment":
            result = assignment_crud.update_status(
                db,
                assignment_id=assignment_id,
                teacher_id=actor.id,
                status="published",
                terminated_reason=None,
            )
            return {"success": True, "resource": result}
        if action_type == "update_assignment":
            # 只投影白名单变更字段：assignmentId 与 beforeSnapshot 绝不进入写路径
            changes = payload.get("changes") or {}
            data = {
                key: changes[key]
                for key in _ASSIGNMENT_UPDATE_ALLOWED_FIELDS
                if key in changes
            }
            if not data:
                raise ValueError("作业更新变更内容不能为空")
            result = assignment_crud.update_assignment(
                db,
                assignment_id=assignment_id,
                teacher_id=actor.id,
                data=data,
            )
            return {"success": True, "resource": result}
        assignment_crud.delete_assignment(
            db,
            assignment_id=assignment_id,
            teacher_id=actor.id,
        )
        return {
            "success": True,
            "resource": {"assignmentId": str(assignment_id), "deleted": True},
        }
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
