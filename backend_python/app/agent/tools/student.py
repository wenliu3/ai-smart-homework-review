"""学生只读工具：身份只从 StudentContext 注入。"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Literal

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database import SessionLocal
from ...models import Assignment, Submission
from ..runtime import RunBudget


class StudentQueryResult(BaseModel):
    status: Literal["ok", "empty", "not_found", "error"]
    title: str
    metrics: dict = Field(default_factory=dict)
    records: list[dict] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass
class StudentContext:
    student_id: int
    budget: RunBudget | None = None


def query_my_learning_overview(
    db: Session,
    actor_id: int,
) -> StudentQueryResult:
    rows = (
        db.query(Submission, Assignment)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .filter(
            Submission.student_id == actor_id,
            Submission.status != "draft",
        )
        .order_by(Submission.updated_at.desc())
        .all()
    )
    if not rows:
        return StudentQueryResult(
            status="empty",
            title="我的学习概况",
            metrics={"submissionCount": 0, "reviewedCount": 0},
        )
    records = [
        {
            "assignmentTitle": assignment.title,
            "status": submission.status,
            "aiScore": submission.ai_score,
            "teacherScore": submission.teacher_score,
            "submittedAt": (
                submission.submitted_at.isoformat()
                if submission.submitted_at
                else None
            ),
        }
        for submission, assignment in rows
    ]
    reviewed = sum(
        1
        for item in records
        if item["teacherScore"] is not None or item["aiScore"] is not None
    )
    return StudentQueryResult(
        status="ok",
        title="我的学习概况",
        metrics={
            "submissionCount": len(records),
            "reviewedCount": reviewed,
        },
        records=records,
        evidence_refs=["mysql://submissions?scope=current_student"],
    )


def query_my_feedback(
    db: Session,
    actor_id: int,
    assignment_id: int,
) -> StudentQueryResult:
    row = (
        db.query(Submission, Assignment)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .filter(
            Submission.student_id == actor_id,
            Submission.assignment_id == assignment_id,
        )
        .first()
    )
    if row is None:
        return StudentQueryResult(
            status="not_found",
            title="我的作业反馈",
            limitations=["未找到本人对该作业的提交"],
        )
    submission, assignment = row
    record = {
        "assignmentTitle": assignment.title,
        "status": submission.status,
        "aiScore": submission.ai_score,
        "aiFeedback": submission.ai_review_content,
        "teacherScore": submission.teacher_score,
        "teacherFeedback": submission.teacher_review_content,
    }
    return StudentQueryResult(
        status="ok",
        title="我的作业反馈",
        records=[record],
        evidence_refs=[
            f"mysql://submissions/{submission.id}?scope=current_student",
        ],
    )


def _safe_tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return StudentQueryResult(
                status="error",
                title="查询失败",
                limitations=["查询暂时失败，请稍后重试"],
            ).model_dump(mode="json")

    return wrapper


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_my_learning_overview(
    runtime: ToolRuntime[StudentContext],
) -> dict:
    """查询当前登录学生本人的提交、评分和学习概况。"""
    with SessionLocal() as db:
        return query_my_learning_overview(
            db,
            actor_id=runtime.context.student_id,
        ).model_dump(mode="json")


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_my_assignment_feedback(
    assignment_id: int,
    runtime: ToolRuntime[StudentContext],
) -> dict:
    """查询当前登录学生本人某次作业的 AI 和教师反馈。

    Args:
        assignment_id: 要查看反馈的作业 ID。
    """
    with SessionLocal() as db:
        return query_my_feedback(
            db,
            actor_id=runtime.context.student_id,
            assignment_id=assignment_id,
        ).model_dump(mode="json")


STUDENT_TOOLS = [get_my_learning_overview, get_my_assignment_feedback]

__all__ = [
    "STUDENT_TOOLS",
    "StudentContext",
    "StudentQueryResult",
    "get_my_assignment_feedback",
    "get_my_learning_overview",
    "query_my_feedback",
    "query_my_learning_overview",
]
