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
from ..database import get_db
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.response import ok
from ..crud import agent_run as agent_run_crud
from ..crud import agent_session as agent_session_crud
from ..crud import agent_approval as agent_approval_crud
from ..crud.action_execution import (
    execute_approved_business_action,
    validate_action_permission,
)
from ..deps import require_roles
from ..models import User
from ..schemas.assistant import (
    ApproveActionRequest,
    CreateActionDraftRequest,
    CreateRunRequest,
    CreateSessionRequest,
    RejectActionRequest,
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
    if not _SESSION_ID_PATTERN.match(req.session_id):
        raise BadRequestException(10011, "session_id 格式非法，需为 8-64 位字母数字/下划线/连字符")
    if agent_session_crud.is_grading_session_id(req.session_id):
        raise BadRequestException(10011, "系统批改会话不支持发起对话")

    request_id = uuid4().hex

    def _stream():
        if actor.role == "teacher":
            events = stream_assistant_events(
                teacher_id=actor.id,
                message=req.message,
                session_id=req.session_id,
                request_id=request_id,
            )
        elif actor.role == "student":
            events = stream_student_events(
                student_id=actor.id,
                message=req.message,
                session_id=req.session_id,
                request_id=request_id,
            )
        else:
            events = stream_admin_events(
                admin_id=actor.id,
                message=req.message,
                session_id=req.session_id,
                request_id=request_id,
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
    if agent_session_crud.is_grading_session_id(run.session_id):
        # 系统批改任务不可由用户取消（否则学生可借取消逃避 AI 批改）
        raise BadRequestException(10011, "系统批改任务不支持取消")
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
