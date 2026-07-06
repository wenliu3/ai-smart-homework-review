"""作业 CRUD"""
from sqlalchemy.orm import Session
from ..models import User, Class, ClassStudent, Assignment, Submission
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.utils import now, camel_to_snake
from ..core.plagiarism import run_plagiarism_check


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


def _class_ids(assignment: Assignment) -> list[int]:
    """从作业的 classes JSON 字段中提取班级 ID 列表"""
    return [int(c["id"]) for c in (assignment.classes or []) if c.get("id")]


# ========== 教师端 ==========

def get_teacher_assignments(db: Session, teacher_id: int, params: dict) -> dict:
    """教师端分页查询自己的作业列表 — 含提交数/已批改数/待批改数等统计"""
    page = int(params.get("page", 1))
    page_size = int(params.get("pageSize", 10))
    sort_by = params.get("sortBy", "createdAt")
    sort_order = params.get("sortOrder", "desc")

    query = db.query(Assignment).filter(Assignment.teacher_id == teacher_id)
    if params.get("status"):
        query = query.filter(Assignment.status == params["status"])
    if params.get("title"):
        query = query.filter(Assignment.title.ilike(f"%{params['title']}%"))
    if params.get("startDate"):
        query = query.filter(Assignment.start_date >= params["startDate"])
    if params.get("endDate"):
        query = query.filter(Assignment.end_date <= params["endDate"])

    total = query.count()
    col = getattr(Assignment, camel_to_snake(sort_by), Assignment.created_at)
    col = col.asc() if sort_order == "asc" else col.desc()
    assignments = query.order_by(col).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for a in assignments:
        cids = _class_ids(a)
        all_students = db.query(ClassStudent).filter(ClassStudent.class_id.in_(cids), ClassStudent.status == "active").count()
        submissions = db.query(Submission).filter(Submission.assignment_id == a.id).count()
        reviewed = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status.in_(["ai_reviewed", "teacher_reviewed"])).count()
        pending = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "submitted").count()
        d = a.to_dict()
        d.update(submissionCount=submissions, totalSubmissions=submissions,
                 reviewedSubmissions=reviewed, pendingSubmissions=pending,
                 totalStudents=all_students, isExpired=bool(a.end_date and now() > a.end_date))
        items.append(d)
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


def get_teacher_detail(db: Session, assignment_id: int) -> dict:
    """获取单个作业详情 — 含提交统计(总数/已批改/待批改/草稿)"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    d = a.to_dict()
    total = db.query(Submission).filter(Submission.assignment_id == a.id).count()
    reviewed = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status.in_(["ai_reviewed", "teacher_reviewed"])).count()
    pending = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "submitted").count()
    draft = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "draft").count()
    all_students = db.query(ClassStudent).filter(ClassStudent.class_id.in_(_class_ids(a)), ClassStudent.status == "active").count()
    d["submissionStats"] = {"totalSubmissions": total, "reviewedSubmissions": reviewed, "pendingSubmissions": pending, "draftSubmissions": draft}
    d["totalStudents"] = all_students
    d["isExpired"] = bool(a.end_date and now() > a.end_date)
    return d


def get_assignment_students(db: Session, assignment_id: int, params: dict) -> dict:
    """查询某作业下的学生提交列表 — 含学生姓名/学号/班级/AI得分/教师得分"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    page = int(params.get("page", 1))
    limit = int(params.get("limit", 20))
    class_id = params.get("classId")
    student_name = params.get("studentName")
    student_number = params.get("studentNumber")

    class_ids = [int(class_id)] if class_id else _class_ids(a)
    max_score = _max_score(a)

    # 查询班级里所有学生(不管有没有提交)
    all_students = db.query(ClassStudent, User).join(
        User, ClassStudent.student_id == User.id
    ).filter(
        ClassStudent.class_id.in_(class_ids),
        ClassStudent.status == "active",
        User.role == "student",
    ).all()

    # 查询该作业所有提交记录,按 student_id 建索引
    submissions = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.class_id.in_(class_ids),
    ).all()
    sub_map = {s.student_id: s for s in submissions}

    # 组装列表: 每个学生一行,有提交的显示提交信息,没提交的显示"未提交"
    all_items = []
    for cs, student in all_students:
        cls = db.query(Class).filter(Class.id == cs.class_id).first()
        s = sub_map.get(student.id)
        if s:
            all_items.append({
                "_id": str(s.id), "studentId": str(s.student_id),
                "studentName": student.name,
                "studentNumber": student.student_id or "",
                "classId": str(s.class_id), "className": cls.name if cls else "",
                "content": s.content, "status": s.status,
                "submittedAt": s.submitted_at.isoformat() if s.submitted_at else None,
                "aiScore": _to100(s.ai_score, max_score), "aiReviewContent": s.ai_review_content,
                "teacherScore": _to100(s.teacher_score, max_score), "teacherReviewContent": s.teacher_review_content,
                "teacherReviewedAt": s.teacher_reviewed_at.isoformat() if s.teacher_reviewed_at else None,
                "wordCount": len(s.content or ""), "attachments": s.attachments or [],
            })
        else:
            # 没提交的学生也显示出来
            all_items.append({
                "_id": None, "studentId": str(student.id),
                "studentName": student.name,
                "studentNumber": student.student_id or "",
                "classId": str(cs.class_id), "className": cls.name if cls else "",
                "content": "", "status": "not_submitted",
                "submittedAt": None, "aiScore": None, "aiReviewContent": None,
                "teacherScore": None, "teacherReviewContent": None,
                "teacherReviewedAt": None, "wordCount": 0, "attachments": [],
            })

    # 按状态过滤
    if params.get("submissionStatus"):
        all_items = [i for i in all_items if i["status"] == params["submissionStatus"]]
    if params.get("gradingStatus"):
        all_items = [i for i in all_items if i["status"] == params["gradingStatus"]]

    # 按姓名/学号过滤
    if student_name:
        all_items = [i for i in all_items if student_name in i["studentName"]]
    if student_number:
        all_items = [i for i in all_items if student_number in (i["studentNumber"] or "")]

    # 排序: 有提交的按提交时间倒序, 未提交的排最后
    all_items.sort(key=lambda x: (x["status"] == "not_submitted", x["submittedAt"] or ""), reverse=False)
    submitted = [i for i in all_items if i["status"] != "not_submitted"]
    not_submitted = [i for i in all_items if i["status"] == "not_submitted"]
    submitted.sort(key=lambda x: x["submittedAt"] or "", reverse=True)
    all_items = submitted + not_submitted

    # 分页
    total = len(all_items)
    paged = all_items[(page - 1) * limit: page * limit]
    return {"items": paged, "total": total, "page": page, "limit": limit, "assignment": a.to_dict()}


def create_assignment(db: Session, teacher_id: int, teacher_name: str, data: dict) -> dict:
    """创建作业 — 根据班级 ID 列表查询班级名称并组装 classes 字段"""
    classes = []
    for cid in data.get("classes", []):
        cls = db.query(Class).filter(Class.id == int(cid)).first()
        if cls:
            classes.append({"id": str(cls.id), "name": cls.name})
    a = Assignment(
        title=data.get("title"), description=data.get("description", ""),
        teacher_id=teacher_id, teacher_name=teacher_name,
        classes=classes, start_date=data.get("startDate"), end_date=data.get("endDate"),
        status="draft", ai_rule=data.get("aiRule"),
    )
    db.add(a)
    db.commit()
    return a.to_dict()


def update_assignment(db: Session, assignment_id: int, teacher_id: int, data: dict) -> dict:
    """更新作业 — 仅作业创建教师可操作"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    if a.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权修改此作业")
    if "classes" in data:
        classes = []
        for cid in data["classes"]:
            cls = db.query(Class).filter(Class.id == int(cid)).first()
            if cls:
                classes.append({"id": str(cls.id), "name": cls.name})
        a.classes = classes
    for k, v in data.items():
        if k == "classes":
            continue
        col = camel_to_snake(k)
        if hasattr(a, col) and col != "id":
            setattr(a, col, v)
    db.commit()
    return a.to_dict()


def update_status(db: Session, assignment_id: int, teacher_id: int, status: str, terminated_reason: str | None) -> dict:
    """更新作业状态(draft/published/terminated) — 终止时可填写原因"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    if a.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此作业")
    a.status = status
    if status == "terminated" and terminated_reason:
        a.terminated_reason = terminated_reason
    db.commit()
    return a.to_dict()


def delete_assignment(db: Session, assignment_id: int, teacher_id: int) -> dict:
    """删除作业 — 同时删除该作业下的所有提交记录"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    if a.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权删除此作业")
    db.query(Submission).filter(Submission.assignment_id == assignment_id).delete()
    db.delete(a)
    db.commit()
    return {"message": "删除成功"}


# ========== 学生端 ==========

def get_student_assignments(db: Session, student_id: int, class_id: str | None, business_status: str | None = None) -> dict:
    """学生端查询已发布的作业列表 — 含每个作业的提交状态(未提交/草稿/已提交/已批改/已过期)"""
    student_classes = db.query(ClassStudent).filter(ClassStudent.student_id == student_id, ClassStudent.status == "active").all()
    all_class_ids = [sc.class_id for sc in student_classes]
    class_ids = [int(class_id)] if (class_id and int(class_id) in all_class_ids) else all_class_ids
    str_class_ids = [str(c) for c in class_ids]
    assignments = db.query(Assignment).filter(Assignment.status == "published").order_by(Assignment.created_at.desc()).all()
    assignments = [a for a in assignments if any(c.get("id") in str_class_ids for c in (a.classes or []))]

    items = []
    for a in assignments:
        submission = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.student_id == student_id).first()
        is_expired = bool(a.end_date and now() > a.end_date)
        has_submitted = bool(submission and submission.status != "draft")
        has_draft = bool(submission and submission.status == "draft")
        is_reviewed = bool(submission and submission.status in ("ai_reviewed", "teacher_reviewed"))

        # 计算 businessStatus(供前端过滤)
        if has_submitted and is_reviewed:
            biz_status = "reviewed"
        elif has_submitted:
            biz_status = "completed"
        elif has_draft:
            biz_status = "draft"
        elif is_expired:
            biz_status = "expired"
        else:
            biz_status = "todo"

        d = a.to_dict()
        d["classId"] = (a.classes[0]["id"] if a.classes else "")
        d["className"] = (a.classes[0]["name"] if a.classes else "")
        d["submissionStatus"] = submission.status if submission else "not_submitted"
        d["submissionId"] = str(submission.id) if submission else None
        d["isExpired"] = is_expired
        d["hasSubmitted"] = has_submitted
        d["hasDraft"] = has_draft
        d["businessStatus"] = biz_status
        items.append(d)

    # 按 businessStatus 过滤
    if business_status and business_status != "all":
        items = [i for i in items if i["businessStatus"] == business_status]

    return {"items": items, "total": len(items)}


def get_student_statistics(db: Session, student_id: int, class_id: str | None) -> dict:
    """学生作业统计 — 总数/已提交/已批改/待办/草稿/已过期"""
    if class_id:
        class_ids = [int(class_id)]
    else:
        student_classes = db.query(ClassStudent).filter(ClassStudent.student_id == student_id, ClassStudent.status == "active").all()
        class_ids = [sc.class_id for sc in student_classes]
    str_class_ids = [str(c) for c in class_ids]
    assignments = db.query(Assignment).filter(Assignment.status == "published").all()
    assignments = [a for a in assignments if any(c.get("id") in str_class_ids for c in (a.classes or []))]

    total = submitted = reviewed = expired = draft = todo = 0
    n = now()
    for a in assignments:
        total += 1
        is_expired = bool(a.end_date and n > a.end_date)
        sub = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.student_id == student_id).first()
        if sub:
            if sub.status == "draft":
                draft += 1
            else:
                submitted += 1
            if sub.status in ("ai_reviewed", "teacher_reviewed"):
                reviewed += 1
            if is_expired and sub.status not in ("ai_reviewed", "teacher_reviewed"):
                expired += 1
        else:
            if is_expired:
                expired += 1
            else:
                todo += 1
    return {"totalAssignments": total, "submittedCount": submitted, "reviewedCount": reviewed,
            "pendingCount": todo, "todoCount": todo, "draftCount": draft, "expiredCount": expired}


def get_student_detail(db: Session, assignment_id: int, student_id: int) -> dict:
    """学生查看作业详情 — 含自己的提交记录"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    submission = db.query(Submission).filter(Submission.assignment_id == assignment_id, Submission.student_id == student_id).first()
    d = a.to_dict()
    d["submission"] = submission.to_dict() if submission else None
    d["isExpired"] = bool(a.end_date and now() > a.end_date)
    return d


# ========== 作业查重 ==========

def check_plagiarism(db: Session, assignment_id: int, teacher_id: int) -> dict:
    """对指定作业的所有学生提交进行查重 — 优先读磁盘原始文件，没有文件则用提交文本"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    if a.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此作业")

    # 拉取该作业所有已提交(非草稿)的记录
    submissions = db.query(Submission).filter(
        Submission.assignment_id == assignment_id,
        Submission.status != "draft",
    ).all()

    if len(submissions) < 2:
        return {
            "results": [],
            "skipped": [],
            "total": len(submissions),
            "suspectCount": 0,
            "passRate": 30,
            "message": "有效提交不足2份，无法进行查重比对",
        }

    import re as _re
    import os as _os
    from ..core.file_parser import extract_file_text
    from ..config import settings

    upload_dir = str(settings.upload_path)
    student_data = []

    for s in submissions:
        student = db.query(User).filter(User.id == s.student_id).first()
        content = ""

        # 优先从磁盘读原始附件文件
        for att in (s.attachments or []):
            file_url = att.get("fileUrl", "")
            filename = file_url.replace("/uploads/", "")
            if filename:
                file_path = _os.path.join(upload_dir, filename)
                if _os.path.exists(file_path):
                    ext = _os.path.splitext(att.get("fileName", ""))[1]
                    text = extract_file_text(file_path, ext)
                    if text and text.strip():
                        content += text + "\n"

        # 如果没附件或文件读不到,用提交的文本内容(去HTML标签)
        if not content.strip():
            content = _re.sub(r"<[^>]*>", "", s.content or "").strip()

        student_data.append({
            "id": s.id,
            "studentName": student.name if student else "",
            "studentNumber": student.student_id if student else "",
            "content": content,
        })

    return run_plagiarism_check(student_data)
