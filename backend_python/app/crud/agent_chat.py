"""教师助手会话消息的数据访问（薄路由、厚 CRUD 约定）。"""
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from ..models import AgentChatMessage


def get_recent_messages(db: Session, teacher_id: int, session_id: str, limit: int = 10) -> list[dict]:
    """最近 N 条消息，按时间正序返回 [{role, content}]，供 Agent 上下文使用。

    id 次级排序保证同秒时间戳下的稳定顺序（save_exchange 两条消息同秒）。
    """
    records = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.teacher_id == teacher_id, AgentChatMessage.session_id == session_id)
        .order_by(AgentChatMessage.created_at.desc(), AgentChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(records)]


def save_exchange(db: Session, teacher_id: int, session_id: str, user_message: str, assistant_message: str) -> None:
    """保存一轮问答（user + assistant 两条）。"""
    db.add(AgentChatMessage(teacher_id=teacher_id, session_id=session_id, role="user", content=user_message))
    db.add(AgentChatMessage(teacher_id=teacher_id, session_id=session_id, role="assistant", content=assistant_message))
    db.commit()


def list_sessions(db: Session, teacher_id: int) -> list[dict]:
    """会话列表：每个 session 的消息数、最后时间、最后一条消息（截断 50 字，camelCase 键）。"""
    LastMsg = aliased(AgentChatMessage)
    last_content = (
        db.query(LastMsg.content)
        .filter(LastMsg.teacher_id == teacher_id, LastMsg.session_id == AgentChatMessage.session_id)
        .order_by(LastMsg.created_at.desc(), LastMsg.id.desc())
        .limit(1)
        .correlate(AgentChatMessage)
        .scalar_subquery()
    )
    sessions = (
        db.query(
            AgentChatMessage.session_id,
            func.count(AgentChatMessage.id).label("message_count"),
            func.max(AgentChatMessage.created_at).label("last_time"),
            last_content.label("last_message"),
        )
        .filter(AgentChatMessage.teacher_id == teacher_id)
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
    return result


def get_session_messages(db: Session, teacher_id: int, session_id: str) -> list[dict]:
    """某个会话的全部消息，按时间正序，camelCase 键。"""
    messages = (
        db.query(AgentChatMessage)
        .filter(AgentChatMessage.teacher_id == teacher_id, AgentChatMessage.session_id == session_id)
        .order_by(AgentChatMessage.created_at.asc(), AgentChatMessage.id.asc())
        .all()
    )
    return [
        {
            "role": m.role,
            "content": m.content,
            "createdAt": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


def delete_session(db: Session, teacher_id: int, session_id: str) -> int:
    """删除指定会话的全部消息，返回删除条数。"""
    deleted = db.query(AgentChatMessage).filter(
        AgentChatMessage.teacher_id == teacher_id,
        AgentChatMessage.session_id == session_id,
    ).delete()
    db.commit()
    return deleted


def delete_all_sessions(db: Session, teacher_id: int) -> int:
    """清空当前教师的全部会话消息，返回删除条数。"""
    deleted = db.query(AgentChatMessage).filter(
        AgentChatMessage.teacher_id == teacher_id,
    ).delete()
    db.commit()
    return deleted
