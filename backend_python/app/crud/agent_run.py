"""PostgreSQL Agent 会话和运行生命周期 CRUD。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AgentRun, AgentSession, AgentStep


def create_session(db: Session, user_id: int, actor_role: str, session_id: str | None = None) -> AgentSession:
    session = AgentSession(id=session_id or uuid4().hex, user_id=user_id, actor_role=actor_role)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def create_run(db: Session, session_id: str, user_id: int, intent: str) -> AgentRun:
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == user_id,
        AgentSession.status == "active",
    ).first()
    if not session:
        raise ValueError("会话不存在或不属于当前用户")
    run = AgentRun(id=uuid4().hex, session_id=session_id, user_id=user_id, intent=intent, started_at=datetime.now())
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def append_step(db: Session, run_id: str, node_name: str, status: str, output: dict | None = None) -> AgentStep:
    last_sequence = db.query(func.max(AgentStep.sequence)).filter(AgentStep.run_id == run_id).scalar() or 0
    step = AgentStep(
        run_id=run_id,
        sequence=last_sequence + 1,
        node_name=node_name,
        status=status,
        output_json=output or {},
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def complete_run(db: Session, run_id: str, final_output: str) -> None:
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise ValueError("运行不存在")
    run.status = "completed"
    run.final_output = final_output
    run.finished_at = datetime.now()
    db.commit()


def get_run(db: Session, run_id: str, user_id: int) -> AgentRun | None:
    return db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.user_id == user_id).first()
