"""教师只读教学数据查询，返回可校验的结构化结果。

每个查询都强制 actor_id 权限隔离：教师只能看到自己名下的班级、作业、学生与提交。
返回结果中绝不包含 password/email/phone 等敏感字段。
"""
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...models import Assignment, Class, ClassStudent, Submission, User


class TeachingQueryResult(BaseModel):
    status: Literal["ok", "empty", "not_found", "error"]
    title: str
    metrics: dict = Field(default_factory=dict)
    records: list[dict] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _student_public_dict(user: User) -> dict:
    """仅暴露非敏感字段（绝不包含 password/email/phone/avatar/meta）。"""
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "studentId": user.student_id,
        "status": user.status,
    }


def query_teacher_classes(db: Session, actor_id: int) -> TeachingQueryResult:
    classes = db.query(Class).filter(Class.teacher_id == actor_id).order_by(Class.created_at.desc()).all()
    if not classes:
        return TeachingQueryResult(status="empty", title="班级列表", metrics={"classCount": 0})
    # id 是当前教师本人名下班级的内部标识，仅供 Agent 工具串联与审批载荷使用；
    # 面向用户的自然语言回答由 prompt 规则约束，绝不展示数据库 ID。
    records = [
        {
            "id": item.id,
            "name": item.name,
            "studentCount": item.student_count or 0,
            "status": item.status,
        }
        for item in classes
    ]
    return TeachingQueryResult(
        status="ok",
        title="班级列表",
        metrics={"classCount": len(records)},
        records=records,
        evidence_refs=["mysql://classes?scope=current_teacher"],
    )


def normalize_business_name(value: str) -> str:
    """业务名称归一化：去除空白、中英文括号、书名号、连字符并忽略大小写。

    用于服务端将模型给出的 className 与数据库班级名做确定性匹配，
    避免依赖模型自行携带班级 ID。
    """
    return re.sub(r"[\s()（）「」【】_-]+", "", value).casefold()


@dataclass
class ClassResolution:
    status: Literal["ok", "not_found", "ambiguous"]
    class_id: int | None = None
    name: str | None = None
    reason: str = ""


def resolve_class_by_business_name(
    db: Session,
    actor_id: int,
    class_name: str,
) -> ClassResolution:
    """服务端按业务名称解析当前教师名下班级——不由 LLM 调用数据库工具。

    匹配规则：
    - 先做归一化后的完整名称匹配，唯一即成功；
    - 无完整匹配时做唯一包含匹配；
    - 未找到或多重匹配 → not_found/ambiguous，绝不猜测；
    - 只查询当前教师名下的班级，其他教师班级不可见。
    """
    target = normalize_business_name(class_name)
    if not target:
        return ClassResolution(status="not_found", reason="班级名称不能为空")
    candidates = db.query(Class).filter(
        Class.teacher_id == actor_id,
    ).all()

    def _pick(items):
        if len(items) == 1:
            return ClassResolution(status="ok", class_id=items[0].id, name=items[0].name)
        if len(items) > 1:
            return ClassResolution(status="ambiguous", reason="存在多个同名候选班级")
        return None

    exact = [c for c in candidates if normalize_business_name(c.name) == target]
    hit = _pick(exact)
    if hit is not None:
        return hit
    contains = [c for c in candidates if target in normalize_business_name(c.name)]
    hit = _pick(contains)
    if hit is not None:
        return hit
    return ClassResolution(status="not_found", reason="未在当前教师名下找到该班级")


def query_class_students(db: Session, actor_id: int, class_id: int) -> TeachingQueryResult:
    """返回当前教师某班级内的 active 学生（必须先验证班级归属）。"""
    cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == actor_id).first()
    if not cls:
        return TeachingQueryResult(status="not_found", title="班级学生")
    links = (
        db.query(ClassStudent)
        .filter(ClassStudent.class_id == class_id, ClassStudent.status == "active")
        .all()
    )
    if not links:
        return TeachingQueryResult(
            status="empty",
            title=f"{cls.name} 学生列表",
            metrics={"studentCount": 0},
        )
    student_ids = [link.student_id for link in links]
    students = db.query(User).filter(User.id.in_(student_ids), User.role == "student").all()
    records = [_student_public_dict(s) for s in students]
    return TeachingQueryResult(
        status="ok",
        title=f"{cls.name} 学生列表",
        metrics={"studentCount": len(records)},
        records=records,
        evidence_refs=[f"mysql://classes/{class_id}/students?scope=current_teacher"],
    )


def query_teacher_assignments(db: Session, actor_id: int) -> TeachingQueryResult:
    assignments = (
        db.query(Assignment)
        .filter(Assignment.alive(), Assignment.teacher_id == actor_id)
        .order_by(Assignment.created_at.desc())
        .all()
    )
    if not assignments:
        return TeachingQueryResult(status="empty", title="作业列表", metrics={"assignmentCount": 0})
    records = [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status,
            "startDate": a.start_date.isoformat() if a.start_date else None,
            "endDate": a.end_date.isoformat() if a.end_date else None,
        }
        for a in assignments
    ]
    return TeachingQueryResult(
        status="ok",
        title="作业列表",
        metrics={"assignmentCount": len(records)},
        records=records,
        evidence_refs=["mysql://assignments?scope=current_teacher"],
    )


def query_assignments_overview(db: Session, actor_id: int) -> TeachingQueryResult:
    """作业概况批量聚合：一次/少量 SQL 返回全部作业的提交与批改统计。

    目的是避免模型对每份历史作业逐个调用 get_my_assignment_summary 造成 N 次扇出。
    只统计当前教师名下的作业。
    """
    assignments = (
        db.query(Assignment)
        .filter(Assignment.alive(), Assignment.teacher_id == actor_id)
        .order_by(Assignment.created_at.desc())
        .all()
    )
    if not assignments:
        return TeachingQueryResult(status="empty", title="作业概况", metrics={"assignmentCount": 0})

    assignment_ids = [a.id for a in assignments]
    status_rows = {
        (row[0], row[1]): row[2]
        for row in db.query(
            Submission.assignment_id,
            Submission.status,
            func.count(Submission.id),
        )
        .filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status != "draft",
        )
        .group_by(Submission.assignment_id, Submission.status)
        .all()
    }

    def _count(aid, status):
        return status_rows.get((aid, status), 0)

    records = [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status,
            "startDate": a.start_date.isoformat() if a.start_date else None,
            "endDate": a.end_date.isoformat() if a.end_date else None,
            "submissionCount": (
                _count(a.id, "submitted")
                + _count(a.id, "ai_reviewed")
                + _count(a.id, "teacher_reviewed")
            ),
            "pendingCount": _count(a.id, "submitted"),
            "aiReviewedCount": _count(a.id, "ai_reviewed"),
            "teacherReviewedCount": _count(a.id, "teacher_reviewed"),
        }
        for a in assignments
    ]
    return TeachingQueryResult(
        status="ok",
        title="作业概况",
        metrics={"assignmentCount": len(records)},
        records=records,
        evidence_refs=["mysql://assignments/overview?scope=current_teacher"],
    )


def query_assignment_summary(db: Session, actor_id: int, assignment_id: int) -> TeachingQueryResult:
    assignment = db.query(Assignment).filter(
        Assignment.alive(),
        Assignment.id == assignment_id,
        Assignment.teacher_id == actor_id,
    ).first()
    if not assignment:
        return TeachingQueryResult(status="not_found", title="作业摘要")
    counts = dict(
        db.query(Submission.status, func.count(Submission.id))
        .filter(Submission.assignment_id == assignment_id, Submission.status != "draft")
        .group_by(Submission.status)
        .all()
    )
    total = sum(counts.values())
    return TeachingQueryResult(
        status="ok",
        title=assignment.title,
        metrics={
            "submissionCount": total,
            "pendingCount": counts.get("submitted", 0),
            "aiReviewedCount": counts.get("ai_reviewed", 0),
            "teacherReviewedCount": counts.get("teacher_reviewed", 0),
        },
        records=[{"title": assignment.title, "status": assignment.status}],
        evidence_refs=[f"mysql://assignments/{assignment_id}?scope=current_teacher"],
    )


def query_student_info(db: Session, actor_id: int, student_name_or_id: str) -> TeachingQueryResult:
    """按 username/name/student_id 模糊查找学生，限定在当前教师班级内。"""
    owned_class_ids = select(Class.id).where(Class.teacher_id == actor_id)
    enrolled_student_ids = select(ClassStudent.student_id).where(
        ClassStudent.class_id.in_(owned_class_ids),
        ClassStudent.status == "active",
    )
    keyword = f"%{student_name_or_id}%"
    students = (
        db.query(User)
        .filter(
            User.id.in_(enrolled_student_ids),
            User.role == "student",
            or_(
                User.username.like(keyword),
                User.name.like(keyword),
                User.student_id.like(keyword),
            ),
        )
        .all()
    )
    if not students:
        return TeachingQueryResult(
            status="not_found",
            title="学生查询",
            metrics={"studentCount": 0},
            limitations=["未匹配到当前教师班级内的学生"],
        )
    records = [_student_public_dict(s) for s in students]
    return TeachingQueryResult(
        status="ok",
        title="学生查询",
        metrics={"studentCount": len(records)},
        records=records,
        evidence_refs=["mysql://users?scope=teacher_enrolled_students"],
    )


def query_teacher_dashboard(db: Session, actor_id: int) -> TeachingQueryResult:
    """教师看板：聚合班级、作业、提交、待批改数。"""
    class_count = (
        db.query(func.count(Class.id)).filter(Class.teacher_id == actor_id).scalar() or 0
    )
    assignment_count = (
        db.query(func.count(Assignment.id))
        .filter(Assignment.alive(), Assignment.teacher_id == actor_id)
        .scalar()
        or 0
    )
    if class_count == 0 and assignment_count == 0:
        return TeachingQueryResult(
            status="empty",
            title="教师看板",
            metrics={"classCount": 0, "assignmentCount": 0},
        )
    own_assignment_ids = select(Assignment.id).where(
        Assignment.alive(), Assignment.teacher_id == actor_id,
    )
    submission_counts = dict(
        db.query(Submission.status, func.count(Submission.id))
        .filter(
            Submission.assignment_id.in_(own_assignment_ids),
            Submission.status != "draft",
        )
        .group_by(Submission.status)
        .all()
    )
    submission_total = sum(submission_counts.values())
    pending_count = submission_counts.get("submitted", 0)
    return TeachingQueryResult(
        status="ok",
        title="教师看板",
        metrics={
            "classCount": class_count,
            "assignmentCount": assignment_count,
            "submissionCount": submission_total,
            "pendingCount": pending_count,
        },
        evidence_refs=["mysql://dashboard?scope=current_teacher"],
    )


def query_pending_reviews(db: Session, actor_id: int) -> TeachingQueryResult:
    """待批改列表：当前教师作业下 status=submitted 的提交。"""
    rows = (
        db.query(Submission, Assignment)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .filter(
            Assignment.alive(),
            Assignment.teacher_id == actor_id,
            Submission.status == "submitted",
        )
        .order_by(Submission.submitted_at.asc())
        .all()
    )
    if not rows:
        return TeachingQueryResult(
            status="empty",
            title="待批改列表",
            metrics={"pendingCount": 0},
        )
    records = [
        {
            "submissionId": sub.id,
            "assignmentId": sub.assignment_id,
            "assignmentTitle": a.title,
            "studentId": sub.student_id,
            "submittedAt": sub.submitted_at.isoformat() if sub.submitted_at else None,
        }
        for sub, a in rows
    ]
    return TeachingQueryResult(
        status="ok",
        title="待批改列表",
        metrics={"pendingCount": len(records)},
        records=records,
        evidence_refs=["mysql://submissions?status=submitted&scope=current_teacher"],
    )

import functools

from langchain.tools import ToolRuntime, tool

from ...database import SessionLocal
from .common import TeacherContext


def serialize_result(result: TeachingQueryResult) -> dict:
    """将 Pydantic 查询结果转换为 JSON 安全字典，保留证据和限制。"""
    return result.model_dump(mode="json")


def _structured_tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return serialize_result(TeachingQueryResult(
                status="error",
                title="查询失败",
                limitations=["查询暂时失败，请稍后再试"],
            ))
    return wrapper


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_classes(runtime: ToolRuntime[TeacherContext]) -> dict:
    """查询当前教师的班级，返回结构化指标、记录和证据引用。"""
    with SessionLocal() as db:
        return serialize_result(query_teacher_classes(db, runtime.context.teacher_id))


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_class_students(
    class_id: int,
    runtime: ToolRuntime[TeacherContext],
) -> dict:
    """查询当前教师指定班级的学生。

    Args:
        class_id: 班级内部标识。
    """
    with SessionLocal() as db:
        return serialize_result(
            query_class_students(db, runtime.context.teacher_id, class_id),
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_assignments(runtime: ToolRuntime[TeacherContext]) -> dict:
    """查询当前教师的作业列表。"""
    with SessionLocal() as db:
        return serialize_result(
            query_teacher_assignments(db, runtime.context.teacher_id),
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_assignment_summary(
    assignment_id: int,
    runtime: ToolRuntime[TeacherContext],
) -> dict:
    """查询当前教师指定作业的提交摘要。

    Args:
        assignment_id: 作业内部标识。
    """
    with SessionLocal() as db:
        return serialize_result(
            query_assignment_summary(
                db, runtime.context.teacher_id, assignment_id,
            ),
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_student(
    student_name_or_id: str,
    runtime: ToolRuntime[TeacherContext],
) -> dict:
    """按姓名或学号查询当前教师班级内的学生。

    Args:
        student_name_or_id: 学生姓名或学号关键词。
    """
    with SessionLocal() as db:
        return serialize_result(
            query_student_info(
                db, runtime.context.teacher_id, student_name_or_id,
            ),
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_dashboard(runtime: ToolRuntime[TeacherContext]) -> dict:
    """查询当前教师看板的聚合指标。"""
    with SessionLocal() as db:
        return serialize_result(
            query_teacher_dashboard(db, runtime.context.teacher_id),
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_pending_reviews(runtime: ToolRuntime[TeacherContext]) -> dict:
    """查询当前教师待批改提交。"""
    with SessionLocal() as db:
        return serialize_result(
            query_pending_reviews(db, runtime.context.teacher_id),
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_structured_tool
def get_my_assignments_overview(runtime: ToolRuntime[TeacherContext]) -> dict:
    """批量查询当前教师全部作业的概况（标题/状态/提交数/待批改数等）。

    查询多个作业时用本工具一次拿全，不要对每份作业逐个调用 get_my_assignment_summary。
    """
    with SessionLocal() as db:
        return serialize_result(
            query_assignments_overview(db, runtime.context.teacher_id),
        )


STRUCTURED_TOOLS = [
    get_my_classes,
    get_my_class_students,
    get_my_assignments,
    get_my_assignments_overview,
    get_my_assignment_summary,
    get_my_student,
    get_my_dashboard,
    get_my_pending_reviews,
]
