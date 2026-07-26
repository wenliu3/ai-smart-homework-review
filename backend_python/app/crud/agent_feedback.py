"""运行反馈落库（PostgreSQL 会话库，规划阶段 4.3）。

(run_id, user_id, source) 唯一：重复反馈按 upsert 覆盖，
先查后写的并发竞态由唯一约束兜底（撞约束回滚重查再更新）。
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AgentFeedback


def _upsert(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    source: str,
    values: dict,
) -> AgentFeedback:
    row = db.query(AgentFeedback).filter(
        AgentFeedback.run_id == run_id,
        AgentFeedback.user_id == user_id,
        AgentFeedback.source == source,
    ).first()
    if row is None:
        row = AgentFeedback(
            run_id=run_id, user_id=user_id, source=source, **values,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.query(AgentFeedback).filter(
                AgentFeedback.run_id == run_id,
                AgentFeedback.user_id == user_id,
                AgentFeedback.source == source,
            ).one()
            for key, value in values.items():
                setattr(row, key, value)
            db.commit()
        db.refresh(row)
        return row
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def submit_user_rating(
    db: Session,
    *,
    run_id: str,
    user_id: int,
    rating: int,
    comment: str | None = None,
) -> AgentFeedback:
    """用户对助手回答的 👍(1)/👎(-1)；同 run 重复评分覆盖。"""
    return _upsert(
        db,
        run_id=run_id,
        user_id=user_id,
        source="user_rating",
        values={"rating": rating, "comment": comment},
    )


def record_teacher_correction(
    db: Session,
    *,
    run_id: str,
    teacher_id: int,
    ai_score: float,
    teacher_score: float,
) -> AgentFeedback:
    """教师改分幅度自动采集：分值按原始分制存，差值 = 教师分 - AI 分。"""
    return _upsert(
        db,
        run_id=run_id,
        user_id=teacher_id,
        source="teacher_correction",
        values={
            "ai_score": ai_score,
            "teacher_score": teacher_score,
            "score_delta": teacher_score - ai_score,
        },
    )


__all__ = ["record_teacher_correction", "submit_user_rating"]
