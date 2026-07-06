"""教师助手 Agent 工具集 — 每个工具封装一个数据库查询能力"""
from dataclasses import dataclass
from langchain.tools import tool, ToolRuntime
from sqlalchemy import func
from ..database import SessionLocal
from ..models import User, Class, ClassStudent, Assignment, Submission


@dataclass
class TeacherContext:
    """每次 agent.invoke()/stream() 时传入，工具通过 runtime.context 访问。
    teacher_id 不出现在任何工具的参数里，LLM 既看不到也填不了这个值，
    从根源上避免"模型自己决定查哪个老师的数据"这种越权风险。

    注意：不传 db session。因为 langgraph 在后台线程里执行工具，
    共享请求线程的 session 会导致 pymysql "Packet sequence number wrong" 错误
    （pymysql 连接不是线程安全的）。每个工具内部用 SessionLocal() 创建独立
    session（独立连接），保证线程安全。"""
    teacher_id: int


# ========== 班级相关 ==========

@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_teacher_classes(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询当前教师的所有班级列表，包含班级名称、学生人数、状态；当教师询问"我有几个班级"或"班级情况"时使用。"""
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        classes = db.query(Class).filter(Class.teacher_id == teacher_id).all()
        if not classes:
            return "您目前没有任何班级。"
        lines = []
        for c in classes:
            lines.append(
                f"- {c.name}(ID:{c.id})，邀请码:{c.code}，"
                f"学生人数:{c.student_count}，状态:{c.status}"
            )
        return f"您共有 {len(classes)} 个班级：\n" + "\n".join(lines)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_class_students(class_id: int, runtime: ToolRuntime[TeacherContext]) -> str:
    """查询指定班级的学生列表，包含姓名、学号、状态；只能查询当前教师自己名下的班级，当教师询问"某班有哪些学生"时使用。

    Args:
        class_id: 班级ID(整数)
    """
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        cls = db.query(Class).filter(
            Class.id == class_id, Class.teacher_id == teacher_id
        ).first()
        if not cls:
            return f"未找到班级ID {class_id}，或该班级不属于您。"
        records = db.query(ClassStudent).filter(
            ClassStudent.class_id == class_id, ClassStudent.status == "active"
        ).all()
        if not records:
            return f"班级「{cls.name}」中暂无活跃学生。"
        # 实时统计每个学生的提交次数（不依赖 ClassStudent.total_submissions 缓存字段，该字段未被维护、恒为 0）
        student_ids = [cs.student_id for cs in records]
        sub_counts = db.query(
            Submission.student_id, func.count(Submission.id)
        ).filter(
            Submission.student_id.in_(student_ids),
            Submission.status != "draft",
        ).group_by(Submission.student_id).all()
        count_map = {sid: cnt for sid, cnt in sub_counts}
        # 批量查询学生信息，消除循环内 N+1 查询
        students = db.query(User).filter(User.id.in_(student_ids)).all()
        student_map = {s.id: s for s in students}
        lines = []
        for cs in records:
            student = student_map.get(cs.student_id)
            if student:
                lines.append(
                    f"- {student.name}，学号:{student.student_id or '无'}，"
                    f"提交次数:{count_map.get(cs.student_id, 0)}"
                )
        return f"班级「{cls.name}」共 {len(records)} 名学生：\n" + "\n".join(lines)


# ========== 作业相关 ==========

@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_teacher_assignments(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询当前教师的所有作业列表，包含标题、状态、截止时间；当教师询问"我的作业"或"发布了几个作业"时使用。"""
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        assignments = db.query(Assignment).filter(
            Assignment.teacher_id == teacher_id
        ).order_by(Assignment.created_at.desc()).all()
        if not assignments:
            return "您目前还没有创建任何作业。"
        lines = []
        for a in assignments:
            classes = "、".join(c.get("name", "") for c in (a.classes or []))
            lines.append(
                f"- 「{a.title}」(ID:{a.id})，状态:{a.status}，"
                f"截止:{a.end_date.strftime('%Y-%m-%d %H:%M') if a.end_date else '无'}，"
                f"关联班级:{classes or '无'}"
            )
        return f"您共有 {len(assignments)} 个作业：\n" + "\n".join(lines)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_assignment_submissions(assignment_id: int, runtime: ToolRuntime[TeacherContext]) -> str:
    """查询某作业下所有学生的提交情况，包含提交状态、AI分数、教师分数；只能查询当前教师自己创建的作业，当教师询问"这个作业交了多少人"或"批改进度"时使用。

    Args:
        assignment_id: 作业ID(整数)
    """
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        assignment = db.query(Assignment).filter(
            Assignment.id == assignment_id, Assignment.teacher_id == teacher_id
        ).first()
        if not assignment:
            return f"未找到作业ID {assignment_id}，或该作业不属于您。"
        submissions = db.query(Submission).filter(
            Submission.assignment_id == assignment_id,
            Submission.status != "draft",
        ).all()
        total = len(submissions)
        if total == 0:
            return f"作业「{assignment.title}」暂无学生提交。"
        ai_reviewed = sum(1 for s in submissions if s.status == "ai_reviewed")
        teacher_reviewed = sum(1 for s in submissions if s.status == "teacher_reviewed")
        pending = sum(1 for s in submissions if s.status == "submitted")
        scores = [s.teacher_score or s.ai_score for s in submissions if (s.teacher_score or s.ai_score) is not None]
        avg = round(sum(scores) / len(scores), 1) if scores else 0

        lines = [f"作业「{assignment.title}」提交情况："]
        lines.append(f"  总提交:{total}，待批改:{pending}，AI已评:{ai_reviewed}，教师已评:{teacher_reviewed}")
        lines.append(f"  平均分:{avg}")
        # 批量查询前10条提交的学生信息，消除 N+1 查询
        display_subs = submissions[:10]
        display_student_ids = [s.student_id for s in display_subs]
        students = db.query(User).filter(User.id.in_(display_student_ids)).all()
        student_map = {s.id: s for s in students}
        for s in display_subs:
            student = student_map.get(s.student_id)
            name = student.name if student else "未知"
            score = s.teacher_score if s.teacher_score is not None else s.ai_score
            lines.append(f"  - {name}，状态:{s.status}，分数:{score}")
        if total > 10:
            lines.append(f"  ...(仅显示前10条，共{total}条)")
        return "\n".join(lines)


# ========== 学生相关 ==========

@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_student_info(student_name_or_id: str, runtime: ToolRuntime[TeacherContext]) -> str:
    """按姓名或学号查询学生信息及其提交记录；只能查询当前教师所带班级中的学生，当教师询问"某学生的信息"或"某某的成绩"时使用。

    Args:
        student_name_or_id: 学生姓名或学号，支持模糊匹配
    """
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        teacher_class_ids = db.query(Class.id).filter(
            Class.teacher_id == teacher_id, Class.status != "disbanded"
        ).all()
        class_ids = [c[0] for c in teacher_class_ids]
        if not class_ids:
            return "您目前没有班级，无法查询学生。"

        teacher_student_ids = db.query(ClassStudent.student_id).filter(
            ClassStudent.class_id.in_(class_ids),
            ClassStudent.status == "active",
        ).distinct().all()
        student_ids = {s[0] for s in teacher_student_ids}
        if not student_ids:
            return "您的班级中暂无学生。"

        kw = f"%{student_name_or_id}%"
        students = db.query(User).filter(
            User.id.in_(student_ids),
            User.role == "student",
            (User.name.ilike(kw)) | (User.student_id.ilike(kw)),
        ).all()
        if not students:
            return f"未在您的班级中找到匹配「{student_name_or_id}」的学生。"
        lines = []
        for stu in students:
            submissions = db.query(Submission).filter(
                Submission.student_id == stu.id,
                Submission.status != "draft",
            ).order_by(Submission.submitted_at.desc()).all()
            lines.append(f"姓名:{stu.name}，学号:{stu.student_id or '无'}，邮箱:{stu.email}")
            if not submissions:
                lines.append("  暂无提交记录")
            else:
                scores = [s.teacher_score or s.ai_score for s in submissions if (s.teacher_score or s.ai_score) is not None]
                avg = round(sum(scores) / len(scores), 1) if scores else 0
                lines.append(f"  总提交:{len(submissions)}，平均分:{avg}")
                # 批量查询前5条提交的作业信息，消除 N+1 查询
                display_subs = submissions[:5]
                assignment_ids = [s.assignment_id for s in display_subs]
                assignments = db.query(Assignment).filter(Assignment.id.in_(assignment_ids)).all()
                assignment_map = {a.id: a for a in assignments}
                for s in display_subs:
                    assignment = assignment_map.get(s.assignment_id)
                    title = assignment.title if assignment else "未知作业"
                    score = s.teacher_score if s.teacher_score is not None else s.ai_score
                    lines.append(f"    - {title}，状态:{s.status}，分数:{score}")
        return "\n".join(lines)


# ========== 统计相关 ==========

@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_teacher_dashboard_stats(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询教师看板统计数据，包含班级数、学生数、作业数、待批改数等；当教师询问"我的教学概况"或"整体数据"时使用。"""
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        my_classes = db.query(Class).filter(
            Class.teacher_id == teacher_id, Class.status == "active"
        ).all()
        class_ids = [c.id for c in my_classes]
        total_students = db.query(ClassStudent).filter(
            ClassStudent.class_id.in_(class_ids), ClassStudent.status == "active"
        ).count()
        my_assignments = db.query(Assignment).filter(Assignment.teacher_id == teacher_id).all()
        assignment_ids = [a.id for a in my_assignments]
        total_submissions = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status != "draft",
        ).count()
        pending = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status.in_(["submitted", "ai_reviewed"]),
        ).count()
        reviewed = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status == "teacher_reviewed",
        ).count()
        return (
            f"教学概况：\n"
            f"  班级数:{len(my_classes)}\n"
            f"  学生总数:{total_students}\n"
            f"  作业总数:{len(my_assignments)}\n"
            f"  提交总数:{total_submissions}\n"
            f"  待批改:{pending}（其中AI已评待人工确认）\n"
            f"  已批改:{reviewed}"
        )


@tool(parse_docstring=True, error_on_invalid_docstring=False)
def get_pending_reviews(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询当前教师的待批改提交列表；当教师询问"有哪些待批改"或"还没改的作业"时使用。"""
    teacher_id = runtime.context.teacher_id
    with SessionLocal() as db:
        my_assignments = db.query(Assignment).filter(
            Assignment.teacher_id == teacher_id
        ).all()
        assignment_ids = [a.id for a in my_assignments]
        pending_subs = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status.in_(["submitted", "ai_reviewed"]),
        ).order_by(Submission.submitted_at.desc()).limit(10).all()
        if not pending_subs:
            return "当前没有待批改的提交。"
        # 批量查询学生和作业信息，消除循环内 2N+1 查询
        student_ids = [s.student_id for s in pending_subs]
        assignment_ids = [s.assignment_id for s in pending_subs]
        students = db.query(User).filter(User.id.in_(student_ids)).all()
        assignments = db.query(Assignment).filter(Assignment.id.in_(assignment_ids)).all()
        student_map = {s.id: s for s in students}
        assignment_map = {a.id: a for a in assignments}
        lines = ["待批改提交："]
        for s in pending_subs:
            student = student_map.get(s.student_id)
            assignment = assignment_map.get(s.assignment_id)
            name = student.name if student else "未知"
            title = assignment.title if assignment else "未知作业"
            submitted = s.submitted_at.strftime("%Y-%m-%d %H:%M") if s.submitted_at else "未知"
            lines.append(f"  - {name} → {title}，提交时间:{submitted}，AI分数:{s.ai_score or '未评'}")
        return "\n".join(lines)


# 工具列表在模块加载时就固定下来 — 供 Agent 使用，不用每次请求重建
ALL_TOOLS = [
    get_teacher_classes,
    get_class_students,
    get_teacher_assignments,
    get_assignment_submissions,
    get_student_info,
    get_teacher_dashboard_stats,
    get_pending_reviews,
]
