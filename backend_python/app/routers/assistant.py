"""新版助手路由（/assistant/runs/*）。

薄路由约定：只做参数校验、依赖注入和响应封装。
所有业务逻辑在 chat_service 和 crud 层。

接口：
- POST   /assistant/runs/stream          启动运行并流式返回 JSON SSE 事件
- GET    /assistant/runs/{run_id}        查询运行状态和详情
- POST   /assistant/runs/{run_id}/cancel 取消运行
- GET    /assistant/sessions             列出当前用户会话
- POST   /assistant/sessions             创建新会话
- GET    /assistant/sessions/{id}/messages 获取会话消息

身份只来自 `require_roles("teacher")`，请求体不接受 user_id/teacher_id/student_id。
"""
import json
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, format_sse_event
from sqlalchemy.orm import Session

from ..agent.service import (
    ChatStreamEvent,
    stream_admin_events,
    stream_assistant_events,
    stream_student_events,
)
from ..agent.tools.approval import create_action_draft
from ..assistant_database import get_assistant_db
from ..config import settings
from ..database import get_db
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.response import ok
from ..crud import agent_run as agent_run_crud
from ..crud import agent_session as agent_session_crud
from ..crud import agent_approval as agent_approval_crud
from ..crud import agent_feedback as agent_feedback_crud
from ..crud.action_execution import (
    execute_approved_business_action,
    validate_action_permission,
)
from ..deps import require_roles
from ..models import User
from ..schemas.assistant import (
    ApproveActionRequest,
    ContentAccessRequest,
    CreateActionDraftRequest,
    CreateRunRequest,
    CreateSessionRequest,
    RejectActionRequest,
    RenameSessionRequest,
    SubmitFeedbackRequest,
)

router = APIRouter()

_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
_RUN_ID_PATTERN = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{64})$")


# ========== 运行流式 ==========

@router.post("/assistant/runs/stream")
def stream_run(
    req: CreateRunRequest,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
):
    """启动一次教师助手运行，以 JSON SSE 流式返回事件。"""
    # 平台开关与教师白名单灰度（规划 5.6）：闸门在流式开始前，返回普通 400
    if not settings.MULTI_AGENT_ENABLED:
        raise BadRequestException(10011, "AI 助手暂未开放，请稍后再试")
    if (
        actor.role == "teacher"
        and not settings.multi_agent_teacher_allowed(actor.id)
    ):
        raise BadRequestException(10011, "AI 助手灰度中，当前账号暂未开放")
    if not _SESSION_ID_PATTERN.match(req.session_id):
        raise BadRequestException(10011, "session_id 格式非法，需为 8-64 位字母数字/下划线/连字符")
    if agent_session_crud.is_system_session_id(req.session_id):
        raise BadRequestException(10011, "系统会话不支持发起对话")

    request_id = uuid4().hex

    def _stream():
        if actor.role == "teacher":
            events = stream_assistant_events(
                teacher_id=actor.id,
                message=req.message,
                session_id=req.session_id,
                request_id=request_id,
                page_context=req.page_context,
            )
        elif actor.role == "student":
            events = stream_student_events(
                student_id=actor.id,
                message=req.message,
                session_id=req.session_id,
                request_id=request_id,
                page_context=req.page_context,
            )
        else:
            events = stream_admin_events(
                admin_id=actor.id,
                message=req.message,
                session_id=req.session_id,
                request_id=request_id,
                page_context=req.page_context,
            )
        for evt in events:
            yield format_sse_event(data_str=evt.data, event=evt.event)

    return EventSourceResponse(_stream())


# ========== 运行查询 ==========

@router.get("/assistant/runs/{run_id}")
def get_run(
    run_id: str,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """查询运行状态和详情。跨用户返回 404。"""
    if not _RUN_ID_PATTERN.match(run_id):
        raise BadRequestException(10011, "run_id 格式非法")

    run = agent_run_crud.get_run(sdb, run_id, user_id=actor.id)
    if not run:
        raise NotFoundException(10015, "运行不存在")
    return ok({
        "runId": run.id,
        "status": run.status,
        "finalOutput": run.final_output,
        "errorCode": run.error_code,
        "intent": run.intent,
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        # 步骤摘要（规划 4.4）：只暴露节点名/状态/耗时/错误码，
        # 不含 output 与证据正文，避免泄露节点内部细节
        "steps": [
            {
                "nodeName": step.node_name,
                "status": step.status,
                "durationMs": step.duration_ms or 0,
                "errorCode": step.error_code,
            }
            for step in sorted(run.steps, key=lambda item: item.sequence)
        ],
    })


# ========== 运行反馈 ==========

@router.post("/assistant/runs/{run_id}/feedback")
def submit_run_feedback(
    run_id: str,
    req: SubmitFeedbackRequest,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """对一次助手运行提交 👍/👎（规划 4.3）。

    只有 run 归属人可评；系统运行（批改/查重）不接受用户评分。
    """
    if not _RUN_ID_PATTERN.match(run_id):
        raise BadRequestException(10011, "run_id 格式非法")
    run = agent_run_crud.get_run(sdb, run_id, user_id=actor.id)
    if run is None:
        raise NotFoundException(10015, "运行不存在")
    if agent_session_crud.is_system_session_id(run.session_id):
        raise BadRequestException(10011, "系统运行不支持评分")
    feedback = agent_feedback_crud.submit_user_rating(
        sdb,
        run_id=run_id,
        user_id=actor.id,
        rating=req.rating,
        comment=req.comment,
    )
    return ok({
        "runId": run_id,
        "rating": feedback.rating,
        "comment": feedback.comment,
    })


# ========== 运行产物 ==========

@router.get("/assistant/runs/{run_id}/artifacts")
def list_run_artifacts(
    run_id: str,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    db: Session = Depends(get_db),
    sdb: Session = Depends(get_assistant_db),
):
    """列出运行产物（分维度批改草案等，规划 3B.3）。

    权限：run 归属人可读；批改 run 的任课教师经
    submission.grading_run_id → assignment → teacher 跨库校验后可读。
    """
    if not _RUN_ID_PATTERN.match(run_id):
        raise BadRequestException(10011, "run_id 格式非法")

    authorized = agent_run_crud.get_run(sdb, run_id, user_id=actor.id) is not None
    if not authorized and actor.role == "teacher":
        from ..models import Assignment, Submission

        owns = (
            db.query(Submission)
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .filter(
                Submission.grading_run_id == run_id,
                Assignment.alive(),
                Assignment.teacher_id == actor.id,
            )
            .first()
        )
        authorized = owns is not None
    if not authorized:
        raise NotFoundException(10015, "运行不存在")

    artifacts = agent_run_crud.list_artifacts_unscoped(sdb, run_id)
    return ok({
        "runId": run_id,
        "items": [
            {
                "artifactType": item.artifact_type,
                "schemaVersion": item.schema_version,
                "payload": item.payload_json,
                "createdAt": (
                    item.created_at.isoformat() if item.created_at else None
                ),
            }
            for item in artifacts
        ],
    })


# ========== 受控正文访问（规格 §14.2） ==========

@router.post("/assistant/admin/runs/{run_id}/content-access")
def admin_run_content_access(
    run_id: str,
    req: ContentAccessRequest,
    actor: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
    sdb: Session = Depends(get_assistant_db),
):
    """管理员受控读取运行正文：必须提供授权理由，且每次访问写操作日志。

    审计日志只记 run_id 与理由，绝不落正文内容。
    """
    if not _RUN_ID_PATTERN.match(run_id):
        raise BadRequestException(10011, "run_id 格式非法")
    reason = req.reason.strip()
    if not reason:
        raise BadRequestException(10011, "必须提供访问理由")
    run = agent_run_crud.get_run_unscoped(sdb, run_id)
    if run is None:
        raise NotFoundException(10015, "运行不存在")

    from ..models import OperationLog

    db.add(OperationLog(
        operator=actor.username,
        operator_name=actor.name,
        action="查询",
        module="运行审计",
        description=f"受控访问运行正文 run_id={run_id}，理由：{reason[:200]}",
        method="POST",
        endpoint=f"/api/assistant/admin/runs/{run_id}/content-access",
        status_code=200,
    ))
    db.commit()

    return ok({
        "runId": run.id,
        "status": run.status,
        "intent": run.intent,
        "finalOutput": run.final_output,
        "sessionId": run.session_id,
        "ownerUserId": run.user_id,
    })


# ========== 取消运行 ==========

@router.post("/assistant/runs/{run_id}/cancel")
def cancel_run(
    run_id: str,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """取消运行。跨用户返回 404。"""
    if not _RUN_ID_PATTERN.match(run_id):
        raise BadRequestException(10011, "run_id 格式非法")

    run = agent_run_crud.get_run(sdb, run_id, user_id=actor.id)
    if not run:
        raise NotFoundException(10015, "运行不存在")
    if agent_session_crud.is_system_session_id(run.session_id):
        # 系统任务（批改/查重解释）不可由用户取消
        # （否则学生可借取消逃避 AI 批改）
        raise BadRequestException(10011, "系统任务不支持取消")
    if run.status in ("completed", "failed", "cancelled"):
        return ok({"runId": run.id, "status": run.status, "message": "运行已结束，无需取消"})
    agent_run_crud.cancel_run(sdb, run_id, user_id=actor.id)
    return ok({"runId": run.id, "status": "cancelled"})


# ========== 会话接口 ==========

@router.get("/assistant/sessions")
def list_sessions(
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """列出当前教师的全部活跃会话。"""
    sessions = agent_session_crud.list_user_sessions(
        sdb,
        user_id=actor.id,
        actor_role=actor.role,
    )
    return ok({
        "sessions": [
            {
                "sessionId": s.id,
                "title": s.title,
                "status": s.status,
                "createdAt": s.created_at.isoformat() if s.created_at else None,
                "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ],
    })


@router.post("/assistant/sessions")
def create_session(
    req: CreateSessionRequest,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """创建新会话。session_id 服务端生成，不接受客户端传入。"""
    session = agent_session_crud.create_session(
        sdb,
        user_id=actor.id,
        actor_role=actor.role,
        title=req.title,
    )
    return ok({"sessionId": session.id, "title": session.title})


@router.delete("/assistant/sessions/{session_id}")
def delete_session(
    session_id: str,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """归档会话（软删除）。跨用户 404；系统会话（批改/查重）不可删。"""
    if agent_session_crud.is_system_session_id(session_id):
        raise BadRequestException(10011, "系统会话不支持删除")
    deleted = agent_session_crud.delete_session(
        sdb, session_id, user_id=actor.id,
    )
    if not deleted:
        raise NotFoundException(10015, "会话不存在")
    return ok({"sessionId": session_id, "status": "archived"})


@router.patch("/assistant/sessions/{session_id}")
def rename_session(
    session_id: str,
    req: RenameSessionRequest,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """重命名会话。跨用户 404；系统会话不可改名。"""
    if agent_session_crud.is_system_session_id(session_id):
        raise BadRequestException(10011, "系统会话不支持改名")
    title = req.title.strip()
    if not title:
        raise BadRequestException(10011, "会话标题不能为空")
    session = agent_session_crud.rename_session(
        sdb, session_id, user_id=actor.id, title=title,
    )
    if session is None:
        raise NotFoundException(10015, "会话不存在")
    return ok({"sessionId": session.id, "title": session.title})


@router.get("/assistant/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    actor: User = Depends(require_roles("teacher", "student", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """获取会话全部消息。跨用户返回空列表。"""
    messages = agent_session_crud.get_session_messages(
        sdb,
        session_id,
        user_id=actor.id,
        actor_role=actor.role,
    )
    return ok({
        "sessionId": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "runId": m.run_id,
                "createdAt": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    })


# ========== 写操作审批 ==========

def _approval_dict(approval):
    return {
        "approvalId": approval.id,
        "runId": approval.run_id,
        "actionType": approval.action_type,
        "targetType": approval.target_type,
        "targetId": approval.target_id,
        "parameters": approval.payload_json,
        "summary": approval.summary,
        "riskLevel": approval.risk_level,
        "status": approval.status,
        "expiresAt": approval.expires_at.isoformat(),
        "result": approval.result_json,
    }


@router.post("/assistant/approvals")
def create_action_approval(
    req: CreateActionDraftRequest,
    actor: User = Depends(require_roles("teacher", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    """保存 Agent 生成的受控写操作草案，不执行任何业务写入。"""
    try:
        if req.run_id and agent_run_crud.get_run(
            sdb, req.run_id, user_id=actor.id,
        ) is None:
            raise ValueError("关联运行不存在或不属于当前用户")
        validate_action_permission(
            req.action_type,
            req.parameters,
            actor.id,
            actor.role,
        )
        draft = create_action_draft(
            action_type=req.action_type,
            target_type=req.target_type,
            target_id=req.target_id,
            parameters=req.parameters,
            summary=req.summary,
            risk_level=(
                # 改分与所有作用于既有对象的作业动作都是高风险；
                # 只有「新建草稿」类动作降为 medium
                "high"
                if req.action_type in {
                    "submit_teacher_score", "update_model_config",
                    "publish_assignment", "update_assignment",
                    "delete_assignment",
                }
                else "medium"
            ),
            ttl_seconds=req.ttl_seconds,
            idempotency_seed=(
                f"{actor.role}:{actor.id}:{req.run_id or 'manual'}"
            ),
        )
        approval = agent_approval_crud.create_approval(
            sdb,
            draft=draft,
            requester_user_id=actor.id,
            requester_role=actor.role,
            run_id=req.run_id,
        )
    except ValueError as exc:
        raise BadRequestException(10011, str(exc)) from exc
    return ok(_approval_dict(approval))


@router.get("/assistant/approvals")
def list_action_approvals(
    status: str | None = None,
    actor: User = Depends(require_roles("teacher", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    approvals = agent_approval_crud.list_owned_approvals(
        sdb,
        user_id=actor.id,
        status=status,
    )
    return ok({"items": [_approval_dict(item) for item in approvals]})


@router.post("/assistant/approvals/{approval_id}/approve")
def approve_action(
    approval_id: str,
    req: ApproveActionRequest,
    actor: User = Depends(require_roles("teacher", "superadmin")),
    db: Session = Depends(get_db),
    sdb: Session = Depends(get_assistant_db),
):
    try:
        result = agent_approval_crud.approve_and_execute(
            sdb,
            approval_id=approval_id,
            actor_user_id=actor.id,
            actor_role=actor.role,
            payload=req.payload,
            permission_checker=lambda action, payload, user_id, role: (
                validate_action_permission(action, payload, user_id, role, db)
            ),
            executor=lambda action, payload, key: (
                execute_approved_business_action(
                    db,
                    actor=actor,
                    action_type=action,
                    payload=payload,
                    idempotency_key=key,
                )
            ),
        )
    except ValueError as exc:
        raise BadRequestException(10011, str(exc)) from exc
    return ok({
        "approvalId": approval_id,
        "status": "executed",
        "result": result,
    })


@router.post("/assistant/approvals/{approval_id}/reject")
def reject_action(
    approval_id: str,
    req: RejectActionRequest,
    actor: User = Depends(require_roles("teacher", "superadmin")),
    sdb: Session = Depends(get_assistant_db),
):
    try:
        approval = agent_approval_crud.reject_approval(
            sdb,
            approval_id=approval_id,
            actor_user_id=actor.id,
            actor_role=actor.role,
            reason=req.reason,
        )
    except ValueError as exc:
        raise BadRequestException(10011, str(exc)) from exc
    return ok(_approval_dict(approval))
