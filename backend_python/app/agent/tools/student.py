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
        .join(
            Assignment,
            (Assignment.id == Submission.assignment_id) & Assignment.alive(),
        )
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
        .join(
            Assignment,
            (Assignment.id == Submission.assignment_id) & Assignment.alive(),
        )
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


# ========== 防代写：题面相似度（服务端专用，绝不注册为 LLM 工具） ==========
# 把题面递给模型等于把题目喂给代写请求，因此查询与比对只在服务端进行。

# 请求与任一进行中作业题面的字符 4-gram 重合率阈值
_TOPIC_MATCH_THRESHOLD = 0.55
_TOPIC_NGRAM = 4
_MIN_MESSAGE_CHARS = 12


def _char_ngrams(text: str, size: int = _TOPIC_NGRAM) -> set[str]:
    compact = "".join(text.split())
    if len(compact) < size:
        return set()
    return {compact[i:i + size] for i in range(len(compact) - size + 1)}


def message_matches_topics(message: str, topics: list[str]) -> bool:
    """确定性判定：学生请求是否与某进行中作业题面高度重合（规划 5.2）。

    以请求侧 n-gram 被题面覆盖的比例衡量——学生整段或大段粘贴题面
    即命中；普通概念提问不受影响。
    """
    message = (message or "").strip()
    if len(message) < _MIN_MESSAGE_CHARS:
        return False
    message_grams = _char_ngrams(message)
    if not message_grams:
        return False
    for topic in topics:
        topic_grams = _char_ngrams(topic or "")
        if not topic_grams:
            continue
        overlap = len(message_grams & topic_grams) / len(message_grams)
        if overlap >= _TOPIC_MATCH_THRESHOLD:
            return True
    return False


def query_active_assignment_topics(db: Session, student_id: int) -> list[str]:
    """学生名下进行中（published 未截止）作业的题面文本。"""
    from ...core.utils import now
    from ...models import ClassStudent

    memberships = db.query(ClassStudent).filter(
        ClassStudent.student_id == student_id,
        ClassStudent.status == "active",
    ).all()
    class_ids = {str(item.class_id) for item in memberships}
    if not class_ids:
        return []
    current = now()
    topics: list[str] = []
    assignments = db.query(Assignment).filter(
        Assignment.alive(),
        Assignment.status == "published",
    ).all()
    for assignment in assignments:
        if assignment.end_date and current > assignment.end_date:
            continue
        assigned = {
            str(item.get("id"))
            for item in (assignment.classes or [])
            if isinstance(item, dict)
        }
        if not (assigned & class_ids):
            continue
        description = (assignment.description or "").strip()
        if description:
            topics.append(description)
    return topics


def build_topic_similarity_checker():
    """构造题面相似度检查闭包；每次调用开独立 Session（后台线程安全）。

    签名 (message, student_id)：容器构造期不知道请求者，
    student_id 由主管在路由时从 state.actor 提供。
    """

    def check(message: str, student_id: int) -> bool:
        if not student_id:
            return False
        with SessionLocal() as db:
            topics = query_active_assignment_topics(db, student_id)
        return message_matches_topics(message, topics)

    return check
