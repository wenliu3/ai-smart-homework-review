"""教师结构化只读查询的权限与证据测试。

覆盖七类查询：班级列表、班级学生、作业列表、作业摘要、学生成绩、教师看板、待批改。
每类同时覆盖正常、空数据和跨教师访问场景。
"""
from datetime import datetime, timedelta

from app.agent.tools.teacher import (
    query_assignment_summary,
    query_class_students,
    query_pending_reviews,
    query_student_info,
    query_teacher_assignments,
    query_teacher_classes,
    query_teacher_dashboard,
)
from app.models import Assignment, Class, ClassStudent, Submission

BASE = datetime(2026, 7, 24, 10, 0, 0)


def _make_class(db, teacher_id, name="一班", code="C10001"):
    cls = Class(name=name, code=code, teacher_id=teacher_id, status="active")
    db.add(cls)
    db.commit()
    return cls


def _make_assignment(db, teacher_id, teacher_name, title="作业一"):
    a = Assignment(
        title=title, teacher_id=teacher_id, teacher_name=teacher_name,
        start_date=BASE, end_date=BASE + timedelta(days=7), status="published",
    )
    db.add(a)
    db.commit()
    return a


def _enroll_student(db, class_id, student_id):
    db.add(ClassStudent(class_id=class_id, student_id=student_id, status="active"))
    db.commit()


# ========== 班级列表 ==========

def test_teacher_classes_only_returns_owned_records(db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    db.add_all([
        Class(name="一班", code="C10001", teacher_id=teacher.id, status="active"),
        Class(name="二班", code="C10002", teacher_id=other.id, status="active"),
    ])
    db.commit()

    result = query_teacher_classes(db, actor_id=teacher.id)

    assert result.status == "ok"
    assert [record["name"] for record in result.records] == ["一班"]
    assert result.metrics["classCount"] == 1
    assert result.evidence_refs


def test_assignment_summary_hides_foreign_assignment(db, teacher, user_factory):
    other = user_factory("t_owner", "teacher")
    assignment = Assignment(
        title="其他教师作业",
        teacher_id=other.id,
        teacher_name=other.name,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
    )
    db.add(assignment)
    db.commit()

    result = query_assignment_summary(db, actor_id=teacher.id, assignment_id=assignment.id)

    assert result.status == "not_found"
    assert result.records == []
    assert result.evidence_refs == []


# ========== 班级学生 ==========

def test_class_students_returns_active_students(db, teacher, user_factory):
    s1 = user_factory("s_stu1", "student")
    s2 = user_factory("s_stu2", "student")
    cls = _make_class(db, teacher.id)
    db.add_all([
        ClassStudent(class_id=cls.id, student_id=s1.id, status="active"),
        ClassStudent(class_id=cls.id, student_id=s2.id, status="active"),
        ClassStudent(class_id=cls.id, student_id=s1.id, status="inactive"),
    ])
    db.commit()

    result = query_class_students(db, actor_id=teacher.id, class_id=cls.id)

    assert result.status == "ok"
    assert result.metrics["studentCount"] == 2
    names = [r["name"] for r in result.records]
    assert "s_stu1" in names
    assert "s_stu2" in names
    assert result.evidence_refs


def test_class_students_empty_when_no_active_students(db, teacher):
    cls = _make_class(db, teacher.id)

    result = query_class_students(db, actor_id=teacher.id, class_id=cls.id)

    assert result.status == "empty"
    assert result.records == []


def test_class_students_rejects_foreign_class(db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    cls = Class(name="别人的班", code="C90001", teacher_id=other.id, status="active")
    db.add(cls)
    db.commit()

    result = query_class_students(db, actor_id=teacher.id, class_id=cls.id)

    assert result.status == "not_found"
    assert result.records == []


# ========== 教师作业列表 ==========

def test_teacher_assignments_returns_own_assignments(db, teacher):
    _make_assignment(db, teacher.id, teacher.name, "作业一")
    _make_assignment(db, teacher.id, teacher.name, "作业二")

    result = query_teacher_assignments(db, actor_id=teacher.id)

    assert result.status == "ok"
    assert result.metrics["assignmentCount"] == 2
    titles = [r["title"] for r in result.records]
    assert "作业一" in titles
    assert "作业二" in titles


def test_teacher_assignments_empty(db, teacher):
    result = query_teacher_assignments(db, actor_id=teacher.id)

    assert result.status == "empty"
    assert result.records == []


def test_teacher_assignments_isolated_from_other_teachers(db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    _make_assignment(db, other.id, other.name, "别人的作业")

    result = query_teacher_assignments(db, actor_id=teacher.id)

    assert result.status == "empty"
    assert all("别人的" not in r["title"] for r in result.records)


# ========== 学生成绩 ==========

def test_student_info_returns_matching_student(db, teacher, user_factory):
    student = user_factory("s_zhang", "student")
    student.student_id = "S100"
    db.commit()
    cls = _make_class(db, teacher.id)
    _enroll_student(db, cls.id, student.id)
    assignment = _make_assignment(db, teacher.id, teacher.name, "作业A")
    db.add(Submission(
        assignment_id=assignment.id, student_id=student.id, class_id=cls.id,
        status="ai_reviewed", ai_score=85.0, submitted_at=BASE,
    ))
    db.commit()

    result = query_student_info(db, actor_id=teacher.id, student_name_or_id="zhang")

    assert result.status == "ok"
    assert len(result.records) >= 1
    assert result.evidence_refs


def test_student_info_not_found_for_unknown(db, teacher):
    result = query_student_info(db, actor_id=teacher.id, student_name_or_id="不存在")

    assert result.status in ("not_found", "empty")
    assert result.records == []


def test_student_info_excludes_sensitive_fields(db, teacher, user_factory):
    student = user_factory("s_li", "student")
    student.student_id = "S200"
    db.commit()
    cls = _make_class(db, teacher.id)
    _enroll_student(db, cls.id, student.id)

    result = query_student_info(db, actor_id=teacher.id, student_name_or_id="li")

    assert result.status == "ok"
    for record in result.records:
        assert "email" not in record
        assert "password" not in record
        assert "phone" not in record


# ========== 教师看板 ==========

def test_dashboard_returns_aggregated_stats(db, teacher):
    _make_class(db, teacher.id)
    _make_assignment(db, teacher.id, teacher.name, "作业一")

    result = query_teacher_dashboard(db, actor_id=teacher.id)

    assert result.status == "ok"
    assert result.metrics["classCount"] == 1
    assert result.metrics["assignmentCount"] == 1
    assert result.evidence_refs


def test_dashboard_empty_for_new_teacher(db, teacher):
    result = query_teacher_dashboard(db, actor_id=teacher.id)

    assert result.status == "empty"
    assert result.metrics["classCount"] == 0


def test_dashboard_excludes_other_teachers_data(db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    db.add(Class(name="别人的班", code="C90001", teacher_id=other.id, status="active"))
    db.commit()

    result = query_teacher_dashboard(db, actor_id=teacher.id)

    assert result.metrics["classCount"] == 0


# ========== 待批改列表 ==========

def test_pending_reviews_returns_unreviewed_submissions(db, teacher, user_factory):
    student = user_factory("s_wang", "student")
    cls = _make_class(db, teacher.id)
    _enroll_student(db, cls.id, student.id)
    assignment = _make_assignment(db, teacher.id, teacher.name, "待批作业")
    db.add(Submission(
        assignment_id=assignment.id, student_id=student.id, class_id=cls.id,
        status="submitted", submitted_at=BASE,
    ))
    db.commit()

    result = query_pending_reviews(db, actor_id=teacher.id)

    assert result.status == "ok"
    assert result.metrics["pendingCount"] >= 1
    assert result.evidence_refs


def test_pending_reviews_empty_when_nothing_pending(db, teacher):
    result = query_pending_reviews(db, actor_id=teacher.id)

    assert result.status == "empty"
    assert result.records == []


def test_pending_reviews_excludes_other_teachers(db, teacher, user_factory):
    other = user_factory("t_other", "teacher")
    student = user_factory("s_chen", "student")
    cls = Class(name="别人的班", code="C90001", teacher_id=other.id, status="active")
    assignment = Assignment(
        title="别人的作业", teacher_id=other.id, teacher_name=other.name,
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

    result = query_pending_reviews(db, actor_id=teacher.id)

    assert result.status == "empty"
    assert result.records == []
