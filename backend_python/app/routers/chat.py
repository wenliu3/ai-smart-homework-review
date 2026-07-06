import logging

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func

logger = logging.getLogger(__name__)

from ..agent import chat_with_agent, _get_agent
from ..models import AgentChatMessage, User
from ..deps import get_current_user
from ..database import SessionLocal, get_db
from ..core.response import ok

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str


@router.post("/teacher/assistant/chat/stream", response_class=EventSourceResponse)
def chat_stream(
    req: ChatRequest,
    teacher: User = Depends(get_current_user),
):
    # 用短事务查历史 + 构建 agent，查询完成后立即释放连接池连接。
    # SSE 流式生成可能耗时 30s+，不能让 get_db 在此期间持有连接。
    with SessionLocal() as db:
        history_records = (
            db.query(AgentChatMessage)
            .filter(AgentChatMessage.teacher_id == teacher.id, AgentChatMessage.session_id == req.session_id)
            .order_by(AgentChatMessage.created_at.desc())
            .limit(10)
            .all()
        )
        chat_history = [{"role": r.role, "content": r.content} for r in reversed(history_records)]
        # 预构建 agent：LLM 客户端是独立的 httpx 连接，不依赖 db session
        agent = _get_agent(db)

    full_answer = ""
    saved = False
    try:
        for content in chat_with_agent(agent, teacher.id, req.message, chat_history):
            full_answer += content
            yield ServerSentEvent(raw_data=content)
        # 流正常结束：用独立短事务落库，确保前端收到 done 时数据已入库
        if full_answer:
            with SessionLocal() as db:
                db.add(AgentChatMessage(
                    teacher_id=teacher.id, session_id=req.session_id,
                    role="user", content=req.message,
                ))
                db.add(AgentChatMessage(
                    teacher_id=teacher.id, session_id=req.session_id,
                    role="assistant", content=full_answer,
                ))
                db.commit()
            saved = True
        yield ServerSentEvent(event="done", raw_data="[DONE]")
    except Exception as e:
        logger.error("Agent chat error: %s", e, exc_info=True)
        yield ServerSentEvent(event="error", raw_data=f"{type(e).__name__}: {e}")
    finally:
        # 异常中断时用独立 session 兜底存储（正常情况已在上面存过，避免重复）
        if full_answer and not saved:
            try:
                with SessionLocal() as db:
                    db.add(AgentChatMessage(
                        teacher_id=teacher.id, session_id=req.session_id,
                        role="user", content=req.message,
                    ))
                    db.add(AgentChatMessage(
                        teacher_id=teacher.id, session_id=req.session_id,
                        role="assistant", content=full_answer,
                    ))
                    db.commit()
            except Exception:
                logger.error("兜底存储失败", exc_info=True)


@router.get("/teacher/assistant/sessions")
def get_sessions(
    teacher: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前教师的会话列表 — 每个 session 返回最后一条消息和时间"""
    # 用关联子查询一次性取出每个 session 的最后一条消息内容，消除 N+1 查询
    LastMsg = aliased(AgentChatMessage)
    last_content = (
        db.query(LastMsg.content)
        .filter(
            LastMsg.teacher_id == teacher.id,
            LastMsg.session_id == AgentChatMessage.session_id,
        )
        .order_by(LastMsg.created_at.desc())
        .limit(1)
        .correlate(AgentChatMessage)
        .as_scalar()
    )

    sessions = (
        db.query(
            AgentChatMessage.session_id,
            func.count(AgentChatMessage.id).label("message_count"),
            func.max(AgentChatMessage.created_at).label("last_time"),
            last_content.label("last_message"),
        )
        .filter(AgentChatMessage.teacher_id == teacher.id)
        .group_by(AgentChatMessage.session_id)
        .order_by(func.max(AgentChatMessage.created_at).desc())
        .all()
    )

    result = []
    for s in sessions:
        content = s.last_message or ""
        result.append({
            "sessionId": s.session_id,
            "messageCount": s.message_count,
            "lastTime": s.last_time.isoformat() if s.last_time else None,
            "lastMessage": (content[:50] + "...") if len(content) > 50 else content,
        })

    return ok({"sessions": result})


@router.get("/teacher/assistant/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    teacher: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取某个会话的全部消息 — 按时间正序排列"""
    messages = (
        db.query(AgentChatMessage)
        .filter(
            AgentChatMessage.teacher_id == teacher.id,
            AgentChatMessage.session_id == session_id,
        )
        .order_by(AgentChatMessage.created_at.asc())
        .all()
    )
    return ok({
        "sessionId": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "createdAt": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    })


@router.delete("/teacher/assistant/sessions/all")
def delete_all_sessions(
    teacher: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清空当前教师的全部会话消息"""
    deleted = db.query(AgentChatMessage).filter(
        AgentChatMessage.teacher_id == teacher.id,
    ).delete()
    db.commit()
    return ok({"message": f"已清空全部会话，共{deleted}条消息"})


@router.delete("/teacher/assistant/sessions/{session_id}")
def delete_session(
    session_id: str,
    teacher: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除指定会话的全部消息"""
    deleted = db.query(AgentChatMessage).filter(
        AgentChatMessage.teacher_id == teacher.id,
        AgentChatMessage.session_id == session_id,
    ).delete()
    db.commit()
    return ok({"message": f"已删除会话，共{deleted}条消息"})