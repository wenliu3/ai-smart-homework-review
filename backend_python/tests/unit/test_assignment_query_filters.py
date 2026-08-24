"""教师作业列表查询过滤测试：className / isExpired。

此前前端搜索表单一直传这两个参数但后端完全忽略（搜索不生效），本文件锁定该修复。
"""
from datetime import datetime, timedelta

import pytest

from app.crud import assignment as assignment_crud
from app.core.utils import now
from app.models import Assignment, Class


@pytest.fixture()
def teacher_classes(db, teacher):
    """教师 A 的两个班级"""
    c1 = Class(name="高一(1)班", code="FILTA1", teacher_id=teacher.id)
    c2 = Class(name="高二(3)班", code="FILTA2", teacher_id=teacher.id)
    db.add_all([c1, c2])
    db.commit()
    return c1, c2


def _make_assignment(db, teacher, cls, title, end_offset_days, status="published"):
    a = Assignment(
        title=title,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(cls.id), "name": cls.name}],
        start_date=datetime.now() - timedelta(days=7),
        end_date=(
            datetime.now() + timedelta(days=end_offset_days)
            if end_offset_days is not None else None
        ),
        status=status,
    )
    db.add(a)
    db.commit()
    return a


@pytest.fixture()
def assignments(db, teacher, teacher_classes):
    c1, c2 = teacher_classes
    # 4 份作业：高一(1)班 x3（一过期两未过期）、高二(3)班 x1（未过期）
    return [
        _make_assignment(db, teacher, c1, "高一旧作业", -1),          # 已过期
        _make_assignment(db, teacher, c1, "高一新作业", 3),           # 未过期
        _make_assignment(db, teacher, c2, "高二作业", 5),             # 未过期
        _make_assignment(db, teacher, c1, "高一远期作业", 30),        # 未过期
    ]


def test_filter_by_class_name(db, teacher, assignments):
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {"className": "高一"})

    titles = [i["title"] for i in result["items"]]
    assert result["total"] == 3
    assert "高二作业" not in titles
    assert set(titles) == {"高一旧作业", "高一新作业", "高一远期作业"}


def test_filter_by_exact_class_name(db, teacher, assignments):
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {"className": "高二(3)班"})

    assert result["total"] == 1
    assert result["items"][0]["title"] == "高二作业"


def test_filter_class_name_no_match(db, teacher, assignments):
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {"className": "不存在的班级"})

    assert result["total"] == 0
    assert result["items"] == []


def test_filter_is_expired_true(db, teacher, assignments):
    """前端 axios 序列化后为字符串 "true"/"false"。"""
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {"isExpired": "true"})

    assert result["total"] == 1
    assert result["items"][0]["title"] == "高一旧作业"


def test_filter_is_expired_false(db, teacher, assignments):
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {"isExpired": "false"})

    titles = {i["title"] for i in result["items"]}
    assert result["total"] == 3
    assert "高一旧作业" not in titles
    assert "高一远期作业" in titles


def test_filter_is_expired_boolean_value(db, teacher, assignments):
    """兼容直接传布尔值的调用方。"""
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {"isExpired": True})

    assert result["total"] == 1
    assert result["items"][0]["title"] == "高一旧作业"


def test_filter_combined_class_and_expired(db, teacher, assignments):
    result = assignment_crud.get_teacher_assignments(
        db, teacher.id, {"className": "高一", "isExpired": "true"},
    )

    assert result["total"] == 1
    assert result["items"][0]["title"] == "高一旧作业"


def test_filter_pagination_after_memory_filter(db, teacher, assignments):
    """内存过滤后分页 total 必须与过滤结果一致。"""
    result = assignment_crud.get_teacher_assignments(
        db, teacher.id, {"className": "高一", "page": 1, "pageSize": 2},
    )

    assert result["total"] == 3
    assert len(result["items"]) == 2


def test_expired_flag_matches_now_comparison(db, teacher, assignments):
    """返回项的 isExpired 字段与过滤口径一致（end_date < now）。"""
    result = assignment_crud.get_teacher_assignments(db, teacher.id, {})
    by_title = {i["title"]: i for i in result["items"]}
    for a in assignments:
        expected = bool(a.end_date and now() > a.end_date)
        assert by_title[a.title]["isExpired"] == expected


def test_sort_by_end_date_desc(db, teacher, assignments):
    result = assignment_crud.get_teacher_assignments(
        db, teacher.id, {"sortBy": "endDate", "sortOrder": "desc"},
    )
    end_dates = [i["endDate"] for i in result["items"] if i["endDate"]]
    assert end_dates == sorted(end_dates, reverse=True)
