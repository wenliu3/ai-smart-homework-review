"""作业 CRUD"""
from sqlalchemy.orm import Session
from ..models import User, Class, ClassStudent, Assignment, Submission
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.utils import now, camel_to_snake
from ..plagiarism import merge_results


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
    """获取单个作业详情 — 含提交统计(总数/已批改/待批改/草稿/AI批改/教师批改)"""
    a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not a:
        raise NotFoundException(10015, "作业不存在")
    d = a.to_dict()
    total = db.query(Submission).filter(Submission.assignment_id == a.id).count()
    reviewed = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status.in_(["ai_reviewed", "teacher_reviewed"])).count()
    pending = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "submitted").count()
    draft = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "draft").count()
    ai_reviewed = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "ai_reviewed").count()
    teacher_reviewed = db.query(Submission).filter(Submission.assignment_id == a.id, Submission.status == "teacher_reviewed").count()
    all_students = db.query(ClassStudent).filter(ClassStudent.class_id.in_(_class_ids(a)), ClassStudent.status == "active").count()
    d["submissionStats"] = {"totalSubmissions": total, "reviewedSubmissions": reviewed, "pendingSubmissions": pending, "draftSubmissions": draft, "aiReviewed": ai_reviewed, "teacherReviewed": teacher_reviewed}
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
                "status": s.status,
                "submittedAt": s.submitted_at.isoformat() if s.submitted_at else None,
                "aiScore": _to100(s.ai_score, max_score), "aiReviewContent": s.ai_review_content,
                "teacherScore": _to100(s.teacher_score, max_score), "teacherReviewContent": s.teacher_review_content,
                "teacherReviewedAt": s.teacher_reviewed_at.isoformat() if s.teacher_reviewed_at else None,
                "wordCount": s.word_count or 0, "attachments": s.attachments or [],
            })
        else:
            # 没提交的学生也显示出来
            all_items.append({
                "_id": None, "studentId": str(student.id),
                "studentName": student.name,
                "studentNumber": student.student_id or "",
                "classId": str(cs.class_id), "className": cls.name if cls else "",
                "status": "not_submitted",
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
        attachments=data.get("attachments", []),
        allow_attachments=data.get("allowAttachments", False),
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

def check_plagiarism(
    db: Session, assignment_id: int, teacher_id: int,
    template_text: str = None,
    template_images: list = None,
    pass_rate: int = None,
    phrase_weight: float = None,
    topic_weight: float = None,
) -> dict:
    """对指定作业的所有学生提交进行查重 — 优先读磁盘原始文件，没有文件则用提交文本
    可选传入模板内容（template_text/template_images），比对前自动剔除模板部分。"""
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

    import os as _os
    import json as _json
    from ..plagiarism import (
        run_plagiarism_check,
        run_image_plagiarism_check,
        extract_file_text,
        extract_all_from_docx as extract_docx_text_and_images,
        get_char_ngram_set,
        PHRASE_NGRAM,
    )
    from ..config import settings

    # 将模板 n-gram 缓存到磁盘，供后续 compare_submissions 排除模板内容
    _template_cache_path = _os.path.join(
        str(settings.upload_path), f"plagiarism_template_{assignment_id}.json"
    )
    if template_text:
        try:
            _template_ngrams = list(get_char_ngram_set(template_text, PHRASE_NGRAM))
            with open(_template_cache_path, "w", encoding="utf-8") as _f:
                _json.dump({"template_ngrams": _template_ngrams}, _f, ensure_ascii=False)
        except Exception:
            pass
    else:
        # 没传模板时清除旧缓存
        if _os.path.exists(_template_cache_path):
            try:
                _os.remove(_template_cache_path)
            except Exception:
                pass

    upload_dir = str(settings.upload_path)
    student_data = []
    image_data = []
    skipped = []

    for s in submissions:
        student = db.query(User).filter(User.id == s.student_id).first()
        content = ""
        all_images = []

        # 优先从磁盘读原始附件文件
        for att in (s.attachments or []):
            file_url = att.get("fileUrl", "")
            filename = file_url.replace("/uploads/", "")
            if filename:
                file_path = _os.path.join(upload_dir, filename)
                if _os.path.exists(file_path):
                    ext = _os.path.splitext(att.get("fileName", ""))[1].lower()
                    if ext == ".docx":
                        # docx: 复用同一个 Document 对象提取全文+图片
                        full_text, images = extract_docx_text_and_images(file_path)
                        if full_text and full_text.strip():
                            content += full_text + "\n"
                        if images:
                            all_images.extend(images)
                    else:
                        text = extract_file_text(file_path, ext)
                        if text and text.strip():
                            content += text + "\n"
                else:
                    # 文件不存在时回退到上传时保存的 textContent
                    text_content = att.get("textContent", "")
                    if text_content and text_content.strip():
                        content += text_content + "\n"

        # 回退到 submission.content 字段（富文本编辑器提交的内容）
        if not content.strip() and s.content:
            content = s.content

        # 内容为空则跳过并记录原因
        if not content.strip():
            skipped.append({
                "studentName": student.name if student else "",
                "studentNumber": student.student_id if student else "",
                "reason": "提交内容为空，无法进行查重比对",
            })
            continue

        student_data.append({
            "id": s.id,
            "studentName": student.name if student else "",
            "studentNumber": student.student_id if student else "",
            "content": content,
        })

        if all_images:
            image_data.append({
                "id": s.id,
                "studentName": student.name if student else "",
                "studentNumber": student.student_id if student else "",
                "images": all_images,
            })

    # 双维度查重 + 合并（文本 + 图片，支持模板剔除）
    text_result = run_plagiarism_check(
        student_data, template_text=template_text,
        pass_rate=pass_rate, phrase_weight=phrase_weight, topic_weight=topic_weight,
    )
    image_result = run_image_plagiarism_check(image_data, template_images=template_images) if len(image_data) >= 2 else None

    return merge_results(text_result, None, image_result, skipped=skipped, pass_rate=pass_rate)


# ========== 对比预览 ==========

def _extract_submission_text(submission, upload_dir: str) -> str:
    """从提交记录中提取全文文本（优先读磁盘原始文件，回退到 content 字段）"""
    import os as _os
    from ..plagiarism import extract_file_text, extract_all_from_docx as extract_docx_all

    text = ""
    for att in (submission.attachments or []):
        file_url = att.get("fileUrl", "")
        filename = file_url.replace("/uploads/", "")
        if filename:
            file_path = _os.path.join(upload_dir, filename)
            if _os.path.exists(file_path):
                ext = _os.path.splitext(att.get("fileName", ""))[1].lower()
                if ext == ".docx":
                    full_text, _ = extract_docx_all(file_path)
                    if full_text and full_text.strip():
                        text += full_text + "\n"
                else:
                    t = extract_file_text(file_path, ext)
                    if t and t.strip():
                        text += t + "\n"
    # 回退到 content 字段
    if not text.strip() and submission.content:
        text = submission.content
    return text


def _extract_submission_html(submission, upload_dir: str) -> str:
    """从提交记录中提取 HTML（docx 用 mammoth 转换，其他用 <pre>，回退到 content）"""
    import os as _os
    from ..plagiarism import file_to_html

    html_parts = []
    has_file = False
    for att in (submission.attachments or []):
        file_url = att.get("fileUrl", "")
        filename = file_url.replace("/uploads/", "")
        if filename:
            file_path = _os.path.join(upload_dir, filename)
            if _os.path.exists(file_path):
                ext = _os.path.splitext(att.get("fileName", ""))[1].lower()
                has_file = True
                h = file_to_html(file_path, ext)
                if h and h.strip():
                    html_parts.append(h)
    # 没有文件附件时回退到 content 字段（富文本 HTML）
    if not has_file and submission.content:
        return submission.content
    return "\n".join(html_parts) if html_parts else "<p>（无内容）</p>"


def _get_submission_file_info(submission, upload_dir: str) -> dict:
    """获取提交记录的第一个文件附件信息（URL、扩展名），用于前端渲染原始 Word。"""
    import os as _os
    for att in (submission.attachments or []):
        file_url = att.get("fileUrl", "")
        filename = file_url.replace("/uploads/", "")
        if filename:
            file_path = _os.path.join(upload_dir, filename)
            if _os.path.exists(file_path):
                ext = _os.path.splitext(att.get("fileName", ""))[1].lower()
                return {"fileUrl": file_url, "ext": ext, "fileName": att.get("fileName", "")}
    return None


def compare_submissions(db: Session, submission_id: int, match_submission_id: int, teacher_id: int) -> dict:
    """获取两份提交的对比预览数据。
    返回: { studentA, studentB, fileA, fileB, contentHtmlA, contentHtmlB, snippets: [...] }
    - fileA/fileB: 文件URL和扩展名（前端用 docx-preview 渲染原始 Word）
    - contentHtmlA/contentHtmlB: 无文件时的富文本 HTML 兑底
    - snippets: 全量公共 N-gram（只保留长度>=PHRASE_NGRAM 的）
    """
    s1 = db.query(Submission).filter(Submission.id == submission_id).first()
    s2 = db.query(Submission).filter(Submission.id == match_submission_id).first()
    if not s1 or not s2:
        raise NotFoundException(10016, "提交记录不存在")

    # 验证老师拥有该作业
    a = db.query(Assignment).filter(Assignment.id == s1.assignment_id).first()
    if not a or a.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此作业")

    import os as _os
    import json as _json
    from ..plagiarism import get_char_ngram_set, PHRASE_NGRAM
    from ..config import settings

    upload_dir = str(settings.upload_path)

    # 纯文本用于计算命中片段
    text_a = _extract_submission_text(s1, upload_dir)
    text_b = _extract_submission_text(s2, upload_dir)

    # 文件信息（供前端渲染原始 Word）
    file_a = _get_submission_file_info(s1, upload_dir)
    file_b = _get_submission_file_info(s2, upload_dir)

    # 无文件时回退到 content 字段
    content_html_a = s1.content if not file_a and s1.content else ""
    content_html_b = s2.content if not file_b and s2.content else ""

    # 加载模板 n-gram 缓存（check_plagiarism 时保存的），用于排除模板内容
    template_ngrams = set()
    _template_cache_path = _os.path.join(upload_dir, f"plagiarism_template_{s1.assignment_id}.json")
    if _os.path.exists(_template_cache_path):
        try:
            with open(_template_cache_path, "r", encoding="utf-8") as _f:
                _cache = _json.load(_f)
            template_ngrams = set(_cache.get("template_ngrams", []))
        except Exception:
            pass

    # 计算全量公共 N-gram，排除模板 n-gram，只保留长度 >= PHRASE_NGRAM 的
    snippets = []
    if text_a and text_b:
        set_a = get_char_ngram_set(text_a, PHRASE_NGRAM)
        set_b = get_char_ngram_set(text_b, PHRASE_NGRAM)
        common = set_a & set_b
        # 排除模板 n-gram
        if template_ngrams:
            common = common - template_ngrams
        snippets = [g for g in common if len(g) >= PHRASE_NGRAM]

    u1 = db.query(User).filter(User.id == s1.student_id).first()
    u2 = db.query(User).filter(User.id == s2.student_id).first()

    return {
        "studentA": {"name": u1.name if u1 else "", "number": u1.student_id if u1 else ""},
        "studentB": {"name": u2.name if u2 else "", "number": u2.student_id if u2 else ""},
        "fileA": file_a,
        "fileB": file_b,
        "contentHtmlA": content_html_a,
        "contentHtmlB": content_html_b,
        "snippets": snippets,
    }
