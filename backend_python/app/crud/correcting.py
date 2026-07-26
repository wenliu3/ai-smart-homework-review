"""批改 CRUD"""
from sqlalchemy.orm import Session
from ..models import User, Class, Assignment, Submission
from ..core.exceptions import NotFoundException
from ..core.utils import now, camel_to_snake


def _max_score(assignment: Assignment) -> int:
    """获取作业的满分值(从 aiRule.maxScore 读取，默认 100)"""
    if assignment.ai_rule and isinstance(assignment.ai_rule, dict):
        return assignment.ai_rule.get("maxScore", 100)
    return 100


def _to100(score, max_score):
    """将原始分数换算为百分制"""
    if score is None:
        return None
    return round((score / max_score) * 100) if max_score > 0 else score


def get_submission_list(db: Session, params: dict) -> dict:
    """教师端分页查询提交列表 — 支持按作业/班级/状态/学生姓名/学号过滤，含学生姓名/学号/得分"""
    page = int(params.get("page", 1))
    limit = int(params.get("limit", 20))
    sort_by = params.get("sortBy", "submittedAt")
    sort_order = params.get("sortOrder", "desc")

    # JOIN User 表，将 studentName/studentNumber 过滤下推到 SQL 层，
    # 确保 total 和分页数据一致（修复原内存过滤导致 total 与页内条数不符的问题）
    # JOIN Assignment 并带 alive()：软删作业不再级联删提交记录，
    # 不在这里过滤的话，已删作业的提交会永远留在批改队列里还能被打分。
    query = (
        db.query(Submission)
        .join(User, Submission.student_id == User.id)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .filter(Assignment.alive())
    )
    if params.get("assignmentId"):
        query = query.filter(Submission.assignment_id == int(params["assignmentId"]))
    if params.get("classId"):
        query = query.filter(Submission.class_id == int(params["classId"]))
    if params.get("status"):
        query = query.filter(Submission.status == params["status"])
    if params.get("studentName"):
        query = query.filter(User.name.ilike(f"%{params['studentName']}%"))
    if params.get("studentNumber"):
        query = query.filter(User.student_id.ilike(f"%{params['studentNumber']}%"))

    total = query.count()
    col = getattr(Submission, camel_to_snake(sort_by), Submission.submitted_at)
    col = col.asc() if sort_order == "asc" else col.desc()
    submissions = query.order_by(col).offset((page - 1) * limit).limit(limit).all()

    items = []
    for s in submissions:
        student = db.query(User).filter(User.id == s.student_id).first()
        cls = db.query(Class).filter(Class.id == s.class_id).first()
        assignment = db.query(Assignment).filter(Assignment.alive(), Assignment.id == s.assignment_id).first()
        max_score = _max_score(assignment) if assignment else 100
        items.append({
            "_id": str(s.id), "assignmentId": str(s.assignment_id), "studentId": str(s.student_id),
            "studentName": student.name if student else "",
            "studentNumber": student.student_id if student else "",
            "classId": str(s.class_id), "className": cls.name if cls else "",
            "wordCount": s.word_count or 0, "content": s.content or "", "status": s.status,
            "submittedAt": s.submitted_at.isoformat() if s.submitted_at else None,
            "aiScore": _to100(s.ai_score, max_score), "aiReviewContent": s.ai_review_content,
            "teacherScore": _to100(s.teacher_score, max_score), "teacherReviewContent": s.teacher_review_content,
            "teacherReviewedAt": s.teacher_reviewed_at.isoformat() if s.teacher_reviewed_at else None,
            "createdAt": s.created_at.isoformat() if s.created_at else None,
            "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
        })

    return {"items": items, "total": total, "page": page, "pageSize": limit}


def get_submission_detail(db: Session, submission_id: int) -> dict:
    """获取单个提交详情 — 含学生信息、班级、附件列表"""
    s = db.query(Submission).filter(Submission.id == submission_id).first()
    if not s:
        raise NotFoundException(10015, "提交记录不存在")
    assignment = db.query(Assignment).filter(Assignment.alive(), Assignment.id == s.assignment_id).first()
    # 作业已软删：不能静默回退成 100 分制照常返回（会把 40/50 显示成 40/100）
    if not assignment:
        raise NotFoundException(10015, "作业不存在")
    student = db.query(User).filter(User.id == s.student_id).first()
    cls = db.query(Class).filter(Class.id == s.class_id).first()
    max_score = _max_score(assignment)
    return {
        "_id": str(s.id), "assignmentId": str(s.assignment_id), "studentId": str(s.student_id),
        "studentName": student.name if student else "",
        "studentNumber": student.student_id if student else "",
        "classId": str(s.class_id), "className": cls.name if cls else "",
        "wordCount": s.word_count or 0, "content": s.content or "", "status": s.status,
        "submittedAt": s.submitted_at.isoformat() if s.submitted_at else None,
        "aiScore": _to100(s.ai_score, max_score), "aiReviewContent": s.ai_review_content,
        "teacherScore": _to100(s.teacher_score, max_score), "teacherReviewContent": s.teacher_review_content,
        "teacherReviewedAt": s.teacher_reviewed_at.isoformat() if s.teacher_reviewed_at else None,
        "gradingRunId": s.grading_run_id,  # 分维度批改产物入口（规划 3B.3）
        "createdAt": s.created_at.isoformat() if s.created_at else None,
        "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
        "attachments": [
            {"fileName": a.get("fileName"), "fileUrl": a.get("fileUrl"),
             "fileSize": a.get("fileSize"), "fileType": a.get("fileType"),
             "textContent": a.get("textContent", "")}
            for a in (s.attachments or [])
        ],
    }


def submit_teacher_review(db: Session, submission_id: int, teacher_score: float, teacher_review_content: str) -> dict:
    """教师提交批改 — 写入教师得分和评语，状态置为 teacher_reviewed"""
    s = db.query(Submission).filter(Submission.id == submission_id).first()
    if not s:
        raise NotFoundException(10015, "提交记录不存在")
    # 作业已软删时提交记录仍在库里（保留可恢复），但不能再产生批改数据
    if db.query(Assignment).filter(
        Assignment.alive(), Assignment.id == s.assignment_id,
    ).first() is None:
        raise NotFoundException(10015, "作业不存在")
    s.teacher_score = teacher_score
    s.teacher_review_content = teacher_review_content
    s.teacher_reviewed_at = now()
    s.status = "teacher_reviewed"
    db.commit()
    return {"success": True, "message": "批改提交成功", "submission": s.to_dict()}
