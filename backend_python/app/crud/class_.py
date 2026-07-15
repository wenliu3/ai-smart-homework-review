"""班级 CRUD"""
import random, string
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import User, Class, ClassStudent, Submission
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.utils import now, camel_to_snake


def _generate_code() -> str:
    """随机生成 6 位班级邀请码(大写字母+数字)"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(6))


def get_list(db: Session, page: int = 1, limit: int = 10, status: str | None = None,
             search: str | None = None, teacher_id: int | None = None,
             sort_field: str = "createdAt", sort_order: str = "desc",
             user_id: int | None = None, user_role: str | None = None) -> dict:
    """分页查询班级列表 — 支持状态/教师过滤、名称/邀请码搜索，并填充教师姓名。

    数据隔离:
      - 学生(user_role='student'): 仅返回通过 ClassStudent 加入的班级
      - 教师(user_role='teacher'): 若未显式指定 teacher_id，默认仅返回自己创建的班级
      - 管理员(user_role='superadmin'): 不做额外过滤
    """
    query = db.query(Class)

    # === 按角色做数据隔离 ===
    if user_role == "student" and user_id:
        # 学生只能看自己加入的班级
        joined_ids = db.query(ClassStudent.class_id).filter(
            ClassStudent.student_id == user_id,
            ClassStudent.status == "active",
        ).subquery()
        query = query.filter(Class.id.in_(joined_ids))
    elif user_role == "teacher":
        if teacher_id:
            # 显式指定了 teacher_id（如管理员查看某教师的班级），按指定值过滤
            query = query.filter(Class.teacher_id == teacher_id)
        elif user_id:
            # 教师默认只看自己创建的班级
            query = query.filter(Class.teacher_id == user_id)
    else:
        # 管理员或其他角色：按 teacher_id 过滤（如有）
        if teacher_id:
            query = query.filter(Class.teacher_id == teacher_id)

    if status:
        query = query.filter(Class.status == status)
    if search:
        kw = f"%{search}%"
        query = query.filter(Class.name.ilike(kw) | Class.code.ilike(kw))
    total = query.count()
    col = getattr(Class, camel_to_snake(sort_field), Class.created_at)
    col = col.asc() if sort_order == "asc" else col.desc()
    items = query.order_by(col).offset((page - 1) * limit).limit(limit).all()
    enriched = []
    for c in items:
        d = c.to_dict()
        teacher = db.query(User).filter(User.id == c.teacher_id).first()
        d["teacherName"] = teacher.name if teacher else ""
        enriched.append(d)
    return {"items": enriched, "total": total, "page": page, "limit": limit}


def get_detail(db: Session, class_id: int) -> dict:
    """获取班级详情 — 含教师姓名"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise NotFoundException(10015, "班级不存在")
    d = cls.to_dict()
    teacher = db.query(User).filter(User.id == cls.teacher_id).first()
    d["teacherName"] = teacher.name if teacher else ""
    return d


def create_class(db: Session, teacher_id: int, data: dict) -> dict:
    """创建班级 — 自动生成唯一邀请码"""
    code = data.get("code") or _generate_code()
    existing = db.query(Class).filter(Class.code == code, Class.status != "disbanded").first()
    if existing:
        raise BadRequestException(10011, "邀请码已被使用，请重新生成")
    cls = Class(
        name=data.get("name"), code=code, teacher_id=teacher_id,
        description=data.get("description", ""), max_students=data.get("maxStudents", 200),
    )
    db.add(cls)
    db.commit()
    return {"message": "班级创建成功", "classId": str(cls.id)}


def update_class(db: Session, class_id: int, teacher_id: int, data: dict) -> dict:
    """更新班级信息 — 仅班级创建教师可操作"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise NotFoundException(10015, "班级不存在")
    if cls.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权修改此班级")
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(cls, col) and col not in ("id", "code"):
            setattr(cls, col, v)
    db.commit()
    return {"message": "更新成功"}


def disband_class(db: Session, class_id: int, teacher_id: int) -> dict:
    """解散班级 — 状态置为 disbanded，所有学生状态置为 left"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise NotFoundException(10015, "班级不存在")
    if cls.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此班级")
    cls.status = "disbanded"
    db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.status == "active").update({ClassStudent.status: "left"})
    db.commit()
    return {"message": "班级已解散"}


def regenerate_code(db: Session, class_id: int, teacher_id: int) -> dict:
    """重新生成班级邀请码"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise NotFoundException(10015, "班级不存在")
    if cls.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此班级")
    cls.code = _generate_code()
    db.commit()
    return {"message": "邀请码已刷新", "inviteCode": cls.code}


def get_students(db: Session, class_id: int, page: int = 1, limit: int = 20,
                 status: str | None = None, search: str | None = None) -> dict:
    """分页查询班级学生列表 — 支持状态过滤、姓名/学号搜索"""
    query = db.query(ClassStudent).filter(ClassStudent.class_id == class_id)
    if status:
        query = query.filter(ClassStudent.status == status)
    class_students = query.all()

    if search:
        kw = f"%{search}%"
        matched = db.query(User).filter(
            User.id.in_([cs.student_id for cs in class_students]),
            (User.name.ilike(kw)) | (User.student_id.ilike(kw)),
        ).all()
        matched_ids = {u.id for u in matched}
        class_students = [cs for cs in class_students if cs.student_id in matched_ids]

    total = len(class_students)
    paged = class_students[(page - 1) * limit: page * limit]
    # 实时统计这页学生的提交次数和最后提交时间（不依赖未维护的缓存字段 total_submissions/last_submission_time）
    page_student_ids = [cs.student_id for cs in paged]
    sub_stats = db.query(
        Submission.student_id,
        func.count(Submission.id).label("cnt"),
        func.max(Submission.submitted_at).label("last_time"),
    ).filter(
        Submission.student_id.in_(page_student_ids),
        Submission.status != "draft",
    ).group_by(Submission.student_id).all()
    stat_map = {sid: (cnt, last) for sid, cnt, last in sub_stats}
    items = []
    for cs in paged:
        student = db.query(User).filter(User.id == cs.student_id).first()
        cnt, last_time = stat_map.get(cs.student_id, (0, None))
        items.append({
            "_id": str(cs.id), "studentId": str(cs.student_id),
            "studentName": student.name if student else "",
            "studentNumber": student.student_id if student else "",
            "avatar": student.avatar if student else "",
            "joinMethod": cs.join_method, "status": cs.status,
            "joinedAt": cs.joined_at.isoformat() if cs.joined_at else None,
            "totalSubmissions": cnt,
            "lastSubmissionTime": last_time.isoformat() if last_time else None,
        })
    return {"items": items, "total": total, "page": page, "limit": limit}


def add_students(db: Session, class_id: int, teacher_id: int, student_ids: list[str]) -> dict:
    """教师批量添加学生到班级 — 校验学生角色、是否已在班、人数上限"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise NotFoundException(10015, "班级不存在")
    if cls.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此班级")
    success, failed = [], []
    for sid in student_ids:
        try:
            sid_int = int(sid)
            student = db.query(User).filter(
                (User.id == sid_int) | (User.student_id == str(sid)),
                User.role == "student",
            ).first()
            if not student:
                failed.append({"id": sid, "reason": "学生不存在或不是学生角色"})
                continue
            existing = db.query(ClassStudent).filter(
                ClassStudent.class_id == class_id, ClassStudent.student_id == student.id,
                ClassStudent.status != "left",
            ).first()
            if existing:
                failed.append({"id": sid, "reason": "学生已在班级中"})
                continue
            active_count = db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.status == "active").count()
            if active_count >= cls.max_students:
                failed.append({"id": sid, "reason": "班级人数已满"})
                continue
            db.add(ClassStudent(class_id=class_id, student_id=student.id, join_method="teacher", status="active", joined_at=now()))
            db.commit()
            success.append(str(student.id))
        except Exception as e:
            db.rollback()
            failed.append({"id": sid, "reason": str(e)})
    count = db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.status == "active").count()
    cls.student_count = count
    db.commit()
    return {"success": success, "failed": failed}


def join_class(db: Session, student_id: int, code: str) -> dict:
    """学生通过邀请码加入班级"""
    cls = db.query(Class).filter(Class.code == code, Class.status == "active").first()
    if not cls:
        raise BadRequestException(10015, "邀请码无效或班级不存在")
    existing = db.query(ClassStudent).filter(
        ClassStudent.class_id == cls.id, ClassStudent.student_id == student_id,
        ClassStudent.status != "left",
    ).first()
    if existing:
        raise BadRequestException(10011, "你已加入此班级")
    active_count = db.query(ClassStudent).filter(ClassStudent.class_id == cls.id, ClassStudent.status == "active").count()
    if active_count >= cls.max_students:
        raise BadRequestException(10011, "班级人数已满")
    db.add(ClassStudent(class_id=cls.id, student_id=student_id, join_method="code", status="active", joined_at=now()))
    cls.student_count = active_count + 1
    db.commit()
    return {"message": "加入班级成功", "classId": str(cls.id), "className": cls.name}


def update_student_status(db: Session, class_id: int, teacher_id: int, student_ids: list[str], status: str) -> dict:
    """教师批量更新班级学生状态(active/inactive/left)"""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise NotFoundException(10015, "班级不存在")
    if cls.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权操作此班级")
    sids = [int(s) for s in student_ids]
    db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.student_id.in_(sids)).update({ClassStudent.status: status})
    count = db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.status == "active").count()
    cls.student_count = count
    db.commit()
    return {"message": "状态更新成功"}


def leave_class(db: Session, class_id: int, student_id: int) -> dict:
    """学生退出班级 — 状态置为 left 并更新班级人数"""
    db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.student_id == student_id).update({ClassStudent.status: "left"})
    count = db.query(ClassStudent).filter(ClassStudent.class_id == class_id, ClassStudent.status == "active").count()
    cls = db.query(Class).filter(Class.id == class_id).first()
    if cls:
        cls.student_count = count
    db.commit()
    return {"message": "已退出班级"}
