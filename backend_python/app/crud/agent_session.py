"""PostgreSQL Agent 会话与消息 CRUD。

会话（AgentSession）和消息（AgentMessage）属于 PostgreSQL Agent 状态库，
不与 MySQL 业务表建立物理外键。`user_id` 是经过服务端鉴权的逻辑引用，
所有写操作必须先校验会话归属当前用户。
"""
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import AgentMessage, AgentSession


def create_session(
    db: Session,
    user_id: int,
    actor_role: str,
    session_id: str | None = None,
    title: str = "新会话",
) -> AgentSession:
    """创建会话。session_id 由调用方提供或自动生成 64 位 hex。"""
    session = AgentSession(
        id=session_id or uuid4().hex,
        user_id=user_id,
        actor_role=actor_role,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _load_owned_session(db: Session, session_id: str, user_id: int) -> AgentSession:
    """加载会话并校验归属；不存在或不属于当前用户则抛 ValueError。"""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == user_id,
        AgentSession.status == "active",
    ).first()
    if not session:
        raise ValueError("会话不存在或不属于当前用户")
    return session


def append_message(
    db: Session,
    session_id: str,
    user_id: int,
    role: str,
    content: str,
    run_id: str | None = None,
    content_type: str = "markdown",
    metadata: dict | None = None,
) -> AgentMessage:
    """向会话追加一条消息，可关联 run_id。跨用户会话拒绝写入。"""
    _load_owned_session(db, session_id, user_id)
    message = AgentMessage(
        session_id=session_id,
        run_id=run_id,
        role=role,
        content=content,
        content_type=content_type,
        metadata_json=metadata or {},
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


GRADING_SESSION_PREFIX = "grading-"
"""系统批改会话的 id 前缀（tasks/grading.py 生成），不属于用户对话会话。"""

# 全部系统会话前缀：不进用户会话列表、不可对话/取消。
# 新增系统任务类型时在此登记（查重解释见 crud/plagiarism_suggestion.py）。
SYSTEM_SESSION_PREFIXES = (GRADING_SESSION_PREFIX, "plagiarism-")


def is_grading_session_id(session_id: str) -> bool:
    """判断是否为系统批改会话 id。"""
    return session_id.startswith(GRADING_SESSION_PREFIX)


def is_system_session_id(session_id: str) -> bool:
    """判断是否为任一系统会话 id（批改/查重解释等）。"""
    return session_id.startswith(SYSTEM_SESSION_PREFIXES)


def list_user_sessions(
    db: Session,
    user_id: int,
    actor_role: str | None = None,
) -> list[AgentSession]:
    """列出用户全部活跃会话（不含系统会话）。"""
    query = db.query(AgentSession).filter(
        AgentSession.user_id == user_id,
        AgentSession.status == "active",
        *[
            AgentSession.id.notlike(f"{prefix}%")
            for prefix in SYSTEM_SESSION_PREFIXES
        ],
    )
    if actor_role is not None:
        query = query.filter(AgentSession.actor_role == actor_role)
    return query.order_by(AgentSession.updated_at.desc()).all()


def get_session_messages(
    db: Session,
    session_id: str,
    user_id: int,
    actor_role: str | None = None,
) -> list[AgentMessage]:
    """获取会话全部消息（按时间正序）。跨用户返回空。"""
    filters = [
        AgentSession.id == session_id,
        AgentSession.user_id == user_id,
    ]
    if actor_role is not None:
        filters.append(AgentSession.actor_role == actor_role)
    owned = db.query(AgentSession).filter(*filters).first()
    if not owned:
        return []
    return (
        db.query(AgentMessage)
        .filter(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at.asc(), AgentMessage.id.asc())
        .all()
    )


def delete_session(db: Session, session_id: str, user_id: int) -> int:
    """软删除会话（status -> archived）。跨用户返回 0。"""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == user_id,
    ).first()
    if not session:
        return 0
    session.status = "archived"
    db.commit()
    return 1


def update_summary(
    db: Session,
    session_id: str,
    user_id: int,
    summary: str,
) -> int:
    """finalize 后写回会话摘要（规划 4.4）。跨用户/已归档返回 0。"""
    updated = (
        db.query(AgentSession)
        .filter(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
            AgentSession.status == "active",
        )
        .update(
            {AgentSession.summary: summary[:500]},
            synchronize_session=False,
        )
    )
    db.commit()
    return updated


def rename_session(
    db: Session,
    session_id: str,
    user_id: int,
    title: str,
) -> AgentSession | None:
    """重命名会话。跨用户返回 None；空标题由路由层校验拒绝。"""
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == user_id,
    ).first()
    if not session:
        return None
    session.title = title
    db.commit()
    db.refresh(session)
    return session
