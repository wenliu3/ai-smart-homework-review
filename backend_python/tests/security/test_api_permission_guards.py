"""接口级权限守卫测试：角色限制与归属校验必须落实在后端。

覆盖：看板角色隔离、菜单/角色管理 superadmin 限制、用户资源自查限制、
教师批改归属、作业详情归属、班级访问控制、AI 规则归属、上传路径穿越防护。
"""
from datetime import datetime, timedelta

import pytest

from app.models import AiRule, Assignment, Class, ClassStudent, Submission


@pytest.fixture()
def superadmin(user_factory):
    return user_factory("admin_root", "superadmin")


@pytest.fixture()
def teacher_b(user_factory):
    return user_factory("t_bob", "teacher")


@pytest.fixture()
def owned_class(db, teacher):
    klass = Class(name="守卫班", code="GUARD1", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    return klass


@pytest.fixture()
def assignment(db, teacher, owned_class):
    a = Assignment(
        title="守卫作业",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(owned_class.id), "name": owned_class.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
    )
    db.add(a)
    db.commit()
    return a


@pytest.fixture()
def submission(db, teacher, student, owned_class, assignment):
    s = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=owned_class.id,
        status="submitted",
        content="学生正文",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ========== 看板角色隔离 ==========

def test_admin_dashboard_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/admin/dashboard/overview", headers=auth_header(student))
    assert response.status_code == 403


def test_admin_dashboard_allowed_for_superadmin(client, superadmin, auth_header):
    response = client.get("/api/admin/dashboard/overview", headers=auth_header(superadmin))
    assert response.status_code == 200


def test_teacher_dashboard_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/teacher/dashboard/stats", headers=auth_header(student))
    assert response.status_code == 403


def test_teacher_dashboard_allowed_for_teacher(client, teacher, auth_header):
    response = client.get("/api/teacher/dashboard/stats", headers=auth_header(teacher))
    assert response.status_code == 200


def test_student_dashboard_forbidden_for_teacher(client, teacher, auth_header):
    response = client.get("/api/student/dashboard/stats", headers=auth_header(teacher))
    assert response.status_code == 403


# ========== 菜单/角色管理仅超级管理员 ==========

def test_menu_management_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/permissions/menus", headers=auth_header(student))
    assert response.status_code == 403


def test_role_management_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/permissions/roles", headers=auth_header(student))
    assert response.status_code == 403


def test_student_cannot_create_menu(client, student, auth_header):
    response = client.post(
        "/api/permissions/menus",
        json={"name": "恶意菜单", "code": "evil", "path": "/evil", "type": "menu"},
        headers=auth_header(student),
    )
    assert response.status_code == 403


def test_role_management_allowed_for_superadmin(client, superadmin, auth_header):
    response = client.get("/api/permissions/roles", headers=auth_header(superadmin))
    assert response.status_code == 200


# ========== 用户资源查询：仅可查自己 ==========

def test_user_resources_cannot_query_others(client, student, teacher, auth_header):
    response = client.get(
        f"/api/permissions/user-roles/users/{teacher.id}/resources",
        headers=auth_header(student),
    )
    assert response.status_code == 403


def test_user_resources_current_allowed(client, student, auth_header):
    response = client.get(
        "/api/permissions/user-roles/users/current/resources",
        headers=auth_header(student),
    )
    assert response.status_code == 200


# ========== 教师批改：角色 + 作业归属 ==========

def test_correcting_list_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/teachers/submissions/list", headers=auth_header(student))
    assert response.status_code == 403


def test_correcting_list_scoped_to_own_assignments(
    client, db, teacher, teacher_b, student, owned_class, assignment, submission, auth_header,
):
    """教师 B 的批改列表不包含教师 A 的提交。"""
    # 教师B自己也有一条提交（另一作业）
    other_class = Class(name="B班", code="GUARD2", teacher_id=teacher_b.id)
    db.add(other_class)
    db.commit()
    other_assignment = Assignment(
        title="B的作业", teacher_id=teacher_b.id, teacher_name=teacher_b.name,
        classes=[{"id": str(other_class.id), "name": other_class.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
    )
    db.add(other_assignment)
    db.commit()
    db.add(Submission(
        assignment_id=other_assignment.id, student_id=student.id,
        class_id=other_class.id, status="submitted", content="B的正文",
    ))
    db.commit()

    resp_b = client.get("/api/teachers/submissions/list", headers=auth_header(teacher_b))
    assert resp_b.status_code == 200
    assert resp_b.json()["data"]["total"] == 1

    resp_a = client.get("/api/teachers/submissions/list", headers=auth_header(teacher))
    assert resp_a.status_code == 200
    assert resp_a.json()["data"]["total"] == 1


def test_correcting_detail_rejects_other_teacher(
    client, teacher_b, submission, auth_header,
):
    response = client.get(
        f"/api/teachers/submissions/detail/{submission.id}",
        headers=auth_header(teacher_b),
    )
    assert response.status_code == 403


def test_correcting_detail_allowed_for_owner(client, teacher, submission, auth_header):
    response = client.get(
        f"/api/teachers/submissions/detail/{submission.id}",
        headers=auth_header(teacher),
    )
    assert response.status_code == 200


def test_correcting_review_rejects_other_teacher(
    client, teacher_b, submission, auth_header,
):
    response = client.post(
        "/api/teachers/submissions/review",
        json={"submissionId": str(submission.id), "teacherScore": 90, "teacherReviewContent": "越权批改"},
        headers=auth_header(teacher_b),
    )
    assert response.status_code == 403


# ========== 作业详情：归属校验 ==========

def test_assignment_detail_rejects_other_teacher(client, teacher_b, assignment, auth_header):
    response = client.get(
        f"/api/teacher/assignments/{assignment.id}", headers=auth_header(teacher_b),
    )
    assert response.status_code == 403


def test_assignment_students_rejects_other_teacher(client, teacher_b, assignment, auth_header):
    response = client.get(
        f"/api/teacher/assignments/{assignment.id}/students", headers=auth_header(teacher_b),
    )
    assert response.status_code == 403


def test_assignment_create_forbidden_for_student(client, student, auth_header):
    response = client.post(
        "/api/teacher/assignments",
        json={"title": "学生建的作业", "classes": []},
        headers=auth_header(student),
    )
    assert response.status_code == 403


# ========== 班级访问控制 ==========

def test_class_detail_rejects_outside_student(client, student, owned_class, auth_header):
    """不在班的学生不能查看班级详情。"""
    response = client.get(f"/api/classes/{owned_class.id}", headers=auth_header(student))
    assert response.status_code == 403


def test_class_detail_allows_member_student(client, db, student, owned_class, auth_header):
    db.add(ClassStudent(
        class_id=owned_class.id, student_id=student.id, status="active", join_method="code",
    ))
    db.commit()

    response = client.get(f"/api/classes/{owned_class.id}", headers=auth_header(student))
    assert response.status_code == 200


def test_class_students_rejects_other_teacher(
    client, teacher_b, owned_class, auth_header,
):
    response = client.get(
        f"/api/classes/{owned_class.id}/students", headers=auth_header(teacher_b),
    )
    assert response.status_code == 403


def test_class_detail_allows_superadmin(client, superadmin, owned_class, auth_header):
    response = client.get(f"/api/classes/{owned_class.id}", headers=auth_header(superadmin))
    assert response.status_code == 200


def test_class_create_forbidden_for_student(client, student, auth_header):
    response = client.post(
        "/api/classes/create",
        json={"name": "学生建的班"},
        headers=auth_header(student),
    )
    assert response.status_code == 403


# ========== AI 规则：角色 + 创建人 + 可见性语义 ==========

def test_ai_rule_create_forbidden_for_student(client, student, auth_header):
    response = client.post(
        "/api/v1/ai-rules",
        json={"name": "学生规则", "modelType": "zhipu", "prompt": "x"},
        headers=auth_header(student),
    )
    assert response.status_code == 403


def test_ai_rule_update_rejects_non_creator(
    client, db, teacher, teacher_b, auth_header,
):
    rule = AiRule(
        name="教师A的规则", model_type="zhipu", prompt="p",
        created_by={"id": str(teacher.id), "name": teacher.name},
    )
    db.add(rule)
    db.commit()

    response = client.post(
        f"/api/v1/ai-rules/{rule.id}/update",
        json={"name": "被篡改的规则"},
        headers=auth_header(teacher_b),
    )
    assert response.status_code == 403


def test_ai_rule_update_allows_superadmin(client, db, teacher, superadmin, auth_header):
    rule = AiRule(
        name="教师A的规则", model_type="zhipu", prompt="p",
        created_by={"id": str(teacher.id), "name": teacher.name},
    )
    db.add(rule)
    db.commit()

    response = client.post(
        f"/api/v1/ai-rules/{rule.id}/update",
        json={"name": "管理员修正"},
        headers=auth_header(superadmin),
    )
    assert response.status_code == 200


@pytest.fixture()
def visibility_rules(db, teacher, superadmin):
    """教师A私有规则 + 教师A公开规则 + 系统规则（超管内置）"""
    rules = [
        AiRule(
            name="A的私有规则", model_type="zhipu", prompt="p", visibility="private",
            created_by={"id": str(teacher.id), "name": teacher.name},
        ),
        AiRule(
            name="A的公开规则", model_type="zhipu", prompt="p", visibility="public",
            created_by={"id": str(teacher.id), "name": teacher.name},
        ),
        AiRule(
            name="系统内置规则", model_type="zhipu", prompt="p", visibility="system",
            created_by={"id": str(superadmin.id), "name": superadmin.name},
        ),
    ]
    db.add_all(rules)
    db.commit()
    return rules


def test_ai_rule_private_hidden_from_other_teacher(
    client, teacher_b, visibility_rules, auth_header,
):
    """私有规则仅创建人与超管可见：教师B列表只看到公开+系统规则。"""
    response = client.get("/api/v1/ai-rules", headers=auth_header(teacher_b))

    assert response.status_code == 200
    names = [i["name"] for i in response.json()["data"]["items"]]
    assert "A的私有规则" not in names
    assert "A的公开规则" in names
    assert "系统内置规则" in names
    assert response.json()["data"]["total"] == 2


def test_ai_rule_private_visible_to_creator(
    client, teacher, visibility_rules, auth_header,
):
    response = client.get("/api/v1/ai-rules", headers=auth_header(teacher))

    names = [i["name"] for i in response.json()["data"]["items"]]
    assert "A的私有规则" in names
    assert response.json()["data"]["total"] == 3


def test_ai_rule_private_visible_to_superadmin(
    client, superadmin, visibility_rules, auth_header,
):
    response = client.get("/api/v1/ai-rules", headers=auth_header(superadmin))

    assert response.json()["data"]["total"] == 3


def test_ai_rule_visibility_filter_respects_isolation(
    client, teacher_b, visibility_rules, auth_header,
):
    """教师B按 private 筛选时看不到教师A的私有规则（结果为空）。"""
    response = client.get(
        "/api/v1/ai-rules", params={"visibility": "private"}, headers=auth_header(teacher_b),
    )

    assert response.json()["data"]["total"] == 0


def test_ai_rule_available_excludes_others_private(
    client, teacher_b, visibility_rules, auth_header,
):
    """创建作业时的规则下拉同样看不到他人私有规则。"""
    response = client.get(
        "/api/v1/ai-rules/available/list", headers=auth_header(teacher_b),
    )

    names = [r["name"] for r in response.json()["data"]]
    assert "A的私有规则" not in names
    assert "A的公开规则" in names


def test_system_rule_only_superadmin_can_manage(
    client, teacher, teacher_b, superadmin, visibility_rules, auth_header,
):
    system_rule = next(r for r in visibility_rules if r.visibility == "system")

    # 教师（含创建该系统规则的超管之外的所有教师）不可改/删/启停
    for actor in (teacher, teacher_b):
        resp_update = client.post(
            f"/api/v1/ai-rules/{system_rule.id}/update",
            json={"name": "x"},
            headers=auth_header(actor),
        )
        resp_toggle = client.post(
            f"/api/v1/ai-rules/{system_rule.id}/toggle-status",
            headers=auth_header(actor),
        )
        resp_delete = client.post(
            f"/api/v1/ai-rules/{system_rule.id}/delete",
            headers=auth_header(actor),
        )
        assert resp_update.status_code == 403
        assert resp_toggle.status_code == 403
        assert resp_delete.status_code == 403

    # 超级管理员可以管理
    resp = client.post(
        f"/api/v1/ai-rules/{system_rule.id}/toggle-status",
        headers=auth_header(superadmin),
    )
    assert resp.status_code == 200


def test_ai_rule_rejects_invalid_visibility(client, teacher, auth_header):
    response = client.post(
        "/api/v1/ai-rules",
        json={"name": "非法可见性", "modelType": "zhipu", "prompt": "x", "visibility": "secret"},
        headers=auth_header(teacher),
    )

    assert response.status_code == 422


# ========== 上传接口：路径穿越防护 ==========

def test_upload_download_rejects_path_traversal(client, student, auth_header):
    """URL 编码的 .. 到达处理器后必须被拒绝（400），而不是解析到上级目录。"""
    response = client.get("/api/upload/download/%2E%2E", headers=auth_header(student))
    assert response.status_code == 400


def test_upload_delete_rejects_path_traversal(client, student, auth_header):
    response = client.delete("/api/upload/delete/%2E%2E", headers=auth_header(student))
    assert response.status_code == 400


def test_upload_plain_dotdot_never_returns_file(client, student, auth_header):
    """未编码的 .. 会被客户端/路由归一化，无论如何不能返回文件内容。"""
    response = client.get("/api/upload/download/..", headers=auth_header(student))
    assert response.status_code != 200


# ========== 模板下载（C 类补实现） ==========

def test_user_import_template_download(client, teacher, auth_header):
    response = client.get("/api/v1/templates/user-import", headers=auth_header(teacher))

    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]


def test_unknown_template_returns_404(client, teacher, auth_header):
    response = client.get("/api/v1/templates/not-exist", headers=auth_header(teacher))

    assert response.status_code == 404


def test_template_download_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/v1/templates/user-import", headers=auth_header(student))

    assert response.status_code == 403
