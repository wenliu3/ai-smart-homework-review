"""教师助手路由（薄路由）：参数校验 + 依赖注入 + 委托 service / crud。"""
import re

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, format_sse_event
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..agent.service import stream_chat_events
from ..assistant_database import get_assistant_db
from ..core.exceptions import BadRequestException
from ..core.response import ok
from ..crud import agent_chat as agent_chat_crud
from ..deps import require_roles
from ..models import User

router = APIRouter()

# session_id 格式：8-64 位字母数字/下划线/连字符
# 前端用 Date.now().toString(36) + Math.random().toString(36) 生成，符合此格式
# 校验防止同一教师用任意字符串拼接历史，也避免特殊字符注入
_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


class ChatRequest(BaseModel):
    message: str
    session_id: str


@router.post("/teacher/assistant/chat/stream")
def chat_stream(
    req: ChatRequest,
    teacher: User = Depends(require_roles("teacher")),
):
    # 端点必须是普通函数（非生成器）：校验要在 SSE 响应开始前执行，非法时异常
    # 才能被全局处理器转为 400。若端点含 yield，校验会被推迟到生成器首次迭代，
    # 届时 200 响应已开始，无法再回 400。
    #
    # 不可在此声明 response_class=EventSourceResponse：FastAPI 0.139 下，一旦声明该
    # response_class，routing 层（routing.py:512 is_sse_stream 分支）会把端点返回值
    # 当作生成器迭代。而本端点是普通函数、返回的是 EventSourceResponse 实例 →
    # 'EventSourceResponse' object is not iterable（TypeError）。
    #
    # 又由于 FastAPI 0.139 的 EventSourceResponse 仅是 StreamingResponse 的 marker
    # 子类（实际 SSE 编码逻辑只在 routing 层的 SSE 分支里），直接
    # EventSourceResponse(generator_of_ServerSentEvent) 行不通——StreamingResponse
    # 会对每个 chunk 调 chunk.encode(charset)，ServerSentEvent 对象没有 encode。
    #
    # 因此这里显式构造 EventSourceResponse，其 content 生成器直接 yield 已序列化的
    # SSE wire-format bytes（复用 FastAPI 内部同一函数 format_sse_event），由
    # StreamingResponse 原样发送。输出与之前 SSE 分支完全一致。
    if not _SESSION_ID_PATTERN.match(req.session_id):
        raise BadRequestException(10011, "session_id 格式非法，需为 8-64 位字母数字/下划线/连字符")

    def _stream():
        for evt in stream_chat_events(teacher.id, req.message, req.session_id):
            # evt.event 为 None 表示默认 message 事件，不输出 event: 行（匹配旧 SSE 分支行为）
            yield format_sse_event(
                data_str=evt.data,
                event=evt.event,
            )

    return EventSourceResponse(_stream())


@router.get("/teacher/assistant/sessions")
def get_sessions(
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """获取当前教师的会话列表 — 每个 session 返回最后一条消息和时间"""
    return ok({"sessions": agent_chat_crud.list_sessions(db, teacher.id)})


@router.get("/teacher/assistant/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """获取某个会话的全部消息 — 按时间正序排列"""
    return ok({
        "sessionId": session_id,
        "messages": agent_chat_crud.get_session_messages(db, teacher.id, session_id),
    })


@router.delete("/teacher/assistant/sessions/all")
def delete_all_sessions(
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """清空当前教师的全部会话消息"""
    deleted = agent_chat_crud.delete_all_sessions(db, teacher.id)
    return ok({"message": f"已清空全部会话，共{deleted}条消息"})


@router.delete("/teacher/assistant/sessions/{session_id}")
def delete_session(
    session_id: str,
    teacher: User = Depends(require_roles("teacher")),
    db: Session = Depends(get_assistant_db),
):
    """删除指定会话的全部消息"""
    deleted = agent_chat_crud.delete_session(db, teacher.id, session_id)
    return ok({"message": f"已删除会话，共{deleted}条消息"})
