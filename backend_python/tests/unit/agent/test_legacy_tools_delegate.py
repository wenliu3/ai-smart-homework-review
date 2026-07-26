"""旧 LangChain 工具委托到结构化查询的回归测试。

任务 1 要求：旧工具保留原工具名和 TeacherContext，但内部改为调用
teacher.py 中的结构化查询函数，避免重复 SQL 和敏感字段泄露。

设计：legacy.py 中每个 @tool 函数只做薄包装，核心逻辑提取成
`format_xxx(ctx, **kwargs) -> str` 函数，可直接测试，不依赖 LangChain
工具调用机制。

重点断言：
- format_student_info 不再返回 email/邮箱/phone/电话（硬约束）。
- 跨教师访问时返回未找到提示，不泄露其他教师数据。
- 各 format_xxx 返回字符串（LangChain 工具协议）。
"""
from datetime import datetime, timedelta

from app.agent.tools import ALL_TOOLS, TeacherContext
from app.agent.tools.common import (
    format_assignment_submissions,
    format_class_students,
    format_student_info,
    format_teacher_assignments,
    format_teacher_classes,
    format_teacher_dashboard_stats,
    format_pending_reviews,
)
from app.models import Assignment, Class, ClassStudent, Submission

BASE = datetime(2026, 7, 24, 10, 0, 0)


def _tool_names() -> set[str]:
    return {t.name for t in ALL_TOOLS}


def test_legacy_tool_names_preserved():
    """原工具名保持不变，避免破坏旧 Prompt 和前端兼容。"""
    expected = {
        "get_teacher_classes",
        "get_class_students",
        "get_teacher_assignments",
        "get_assignment_submissions",
        "get_student_info",
        "get_teacher_dashboard_stats",
        "get_pending_reviews",
    }
    assert expected.issubset(_tool_names())


# ========== 班级列表 ==========

def test_format_teacher_classes_returns_string(db, teacher):
    db.add(Class(name="一班", code="C10001", teacher_id=teacher.id, status="active"))
    db.commit()

    result = format_teacher_classes(TeacherContext(teacher_id=teacher.id))

    assert isinstance(result, str)
    assert "一班" in result
    assert "1" in result  # 班级数量


def test_format_teacher_classes_empty(db, teacher):
    result = format_teacher_classes(TeacherContext(teacher_id=teacher.id))
    assert "没有" in result or "0" in result


# ========== 班级学生 ==========

def test_format_class_students_returns_students(db, teacher, user_factory):
    s1 = user_factory("s_zhang", "student")
    cls = Class(name="一班", code="C10001", teacher_id=teacher.id, status="active")
    db.add(cls)
    db.commit()
    db.add(ClassStudent(class_id=cls.id, student_id=s1.id, status="active"))
    db.commit()

    result = format_class_students(
        TeacherContext(teacher_id=teacher.id), class_id=cls.id
    )

    assert isinstance(result, str)
    assert "s_zhang" in result or "zhang" in result


def test_format_class_students_rejects_foreign_class(db, teacher, user_factory):
    """跨教师查询班级学生时，返回未找到提示。"""
    other = user_factory("t_other", "teacher")
    cls = Class(name="别人的班", code="C90001", teacher_id=other.id, status="active")
    db.add(cls)
    db.commit()

    result = format_class_students(
        TeacherContext(teacher_id=teacher.id), class_id=cls.id
    )

    assert "未找到" in result or "不属于" in result


def test_format_class_students_does_not_leak_email(db, teacher, user_factory):
    """班级学生工具不得返回 email/邮箱/phone/电话。"""
    student = user_factory("s_li", "student")
    cls = Class(name="一班", code="C10001", teacher_id=teacher.id, status="active")
    db.add(cls)
    db.commit()
    db.add(ClassStudent(class_id=cls.id, student_id=student.id, status="active"))
    db.commit()

    result = format_class_students(
        TeacherContext(teacher_id=teacher.id), class_id=cls.id
    )

    assert "email" not in result.lower()
    assert "邮箱" not in result
    assert "phone" not in result.lower()
    assert "电话" not in result
    assert "password" not in result.lower()


# ========== 作业列表 ==========

def test_format_teacher_assignments_returns_titles(db, teacher):
    db.add(Assignment(
        title="作业一", teacher_id=teacher.id, teacher_name=teacher.name,
        start_date=BASE, end_date=BASE + timedelta(days=7), status="published",
    ))
    db.commit()

    result = format_teacher_assignments(TeacherContext(teacher_id=teacher.id))

    assert isinstance(result, str)
    assert "作业一" in result


def test_format_teacher_assignments_empty(db, teacher):
    result = format_teacher_assignments(TeacherContext(teacher_id=teacher.id))
    assert "没有" in result or "0" in result


# ========== 作业提交摘要 ==========

def test_format_assignment_submissions_returns_summary(db, teacher, user_factory):
    student = user_factory("s_wang", "student")
    cls = Class(name="一班", code="C10001", teacher_id=teacher.id, status="active")
    assignment = Assignment(
        title="作业一", teacher_id=teacher.id, teacher_name=teacher.name,
        start_date=BASE, end_date=BASE + timedelta(days=7), status="published",
    )
    db.add_all([cls, assignment])
    db.commit()
    db.add_all([
        ClassStudent(class_id=cls.id, student_id=student.id, status="active"),
        Submission(
            assignment_id=assignment.id, student_id=student.id, class_id=cls.id,
            status="submitted", submitted_at=BASE,
        ),
    ])
    db.commit()

    result = format_assignment_submissions(
        TeacherContext(teacher_id=teacher.id), assignment_id=assignment.id
    )

    assert isinstance(result, str)
    assert "作业一" in result
    assert "1" in result  # 提交数量


def test_format_assignment_submissions_rejects_foreign(db, teacher, user_factory):
    """跨教师查询作业提交时，返回未找到提示。"""
    other = user_factory("t_other", "teacher")
    assignment = Assignment(
        title="别人的作业", teacher_id=other.id, teacher_name=other.name,
        start_date=BASE, end_date=BASE + timedelta(days=7), status="published",
    )
    db.add(assignment)
    db.commit()

    result = format_assignment_submissions(
        TeacherContext(teacher_id=teacher.id), assignment_id=assignment.id
    )

    assert "未找到" in result or "不属于" in result


# ========== 学生信息 ==========

def test_format_student_info_does_not_leak_email(db, teacher, user_factory):
    """format_student_info 不得返回 email/邮箱/phone/电话 等敏感字段。"""
    student = user_factory("s_zhang", "student")
    student.student_id = "S100"
    db.commit()
    cls = Class(name="一班", code="C10001", teacher_id=teacher.id, status="active")
    db.add(cls)
    db.commit()
    db.add(ClassStudent(class_id=cls.id, student_id=student.id, status="active"))
    db.commit()

    result = format_student_info(
        TeacherContext(teacher_id=teacher.id), student_name_or_id="zhang"
    )

    assert isinstance(result, str)
    assert "email" not in result.lower()
    assert "邮箱" not in result
    assert "phone" not in result.lower()
    assert "电话" not in result
    assert "password" not in result.lower()


def test_format_student_info_foreign_teacher_returns_not_found(db, teacher, user_factory):
    """跨教师查询学生时，返回未找到提示，不泄露其他教师的学生数据。"""
    other = user_factory("t_other", "teacher")
    student = user_factory("s_private", "student")
    student.student_id = "S200"
    db.commit()
    cls = Class(name="别人的班", code="C90001", teacher_id=other.id, status="active")
    db.add(cls)
    db.commit()
    db.add(ClassStudent(class_id=cls.id, student_id=student.id, status="active"))
    db.commit()

    result = format_student_info(
        TeacherContext(teacher_id=teacher.id), student_name_or_id="private"
    )

    assert "未找到" in result or "无" in result
    assert "s_private" not in result


def test_format_student_info_returns_student(db, teacher, user_factory):
    """学生信息工具返回学生基本信息（不含敏感字段）。"""
    student = user_factory("s_chen", "student")
    student.student_id = "S300"
    db.commit()
    cls = Class(name="一班", code="C10001", teacher_id=teacher.id, status="active")
    db.add(cls)
    db.commit()
    db.add(ClassStudent(class_id=cls.id, student_id=student.id, status="active"))
    db.commit()

    result = format_student_info(
        TeacherContext(teacher_id=teacher.id), student_name_or_id="chen"
    )

    assert "s_chen" in result or "chen" in result
    assert "S300" in result  # 学号


# ========== 教师看板 ==========

def test_format_teacher_dashboard_stats_returns_aggregate(db, teacher):
    db.add(Class(name="一班", code="C10001", teacher_id=teacher.id, status="active"))
    db.add(Assignment(
        title="作业一", teacher_id=teacher.id, teacher_name=teacher.name,
        start_date=BASE, end_date=BASE + timedelta(days=7), status="published",
    ))
    db.commit()

    result = format_teacher_dashboard_stats(TeacherContext(teacher_id=teacher.id))

    assert isinstance(result, str)
    assert "1" in result  # 班级数和作业数


def test_format_teacher_dashboard_stats_empty(db, teacher):
    result = format_teacher_dashboard_stats(TeacherContext(teacher_id=teacher.id))
    assert "0" in result


# ========== 待批改 ==========

def test_format_pending_reviews_returns_pending(db, teacher, user_factory):
    student = user_factory("s_li", "student")
    cls = Class(name="一班", code="C10001", teacher_id=teacher.id, status="active")
    assignment = Assignment(
        title="待批作业", teacher_id=teacher.id, teacher_name=teacher.name,
        start_date=BASE, end_date=BASE + timedelta(days=7), status="published",
    )
    db.add_all([cls, assignment])
    db.commit()
    db.add_all([
        ClassStudent(class_id=cls.id, student_id=student.id, status="active"),
        Submission(
            assignment_id=assignment.id, student_id=student.id, class_id=cls.id,
            status="submitted", submitted_at=BASE,
        ),
    ])
    db.commit()

    result = format_pending_reviews(TeacherContext(teacher_id=teacher.id))

    assert isinstance(result, str)
    assert "待批" in result or "待批改" in result


def test_format_pending_reviews_empty(db, teacher):
    result = format_pending_reviews(TeacherContext(teacher_id=teacher.id))
    assert "没有" in result or "0" in result or "无" in result
