"""用户管理接口契约测试：服务端参数校验、鉴权、角色-学号一致性、唯一性。

覆盖要求（见接口审计任务）：
- 学生缺少学号 / 非法邮箱 / 密码不足6位 / 空用户名 / 空姓名 / 非法角色 / 非法状态 /
  手机号格式错误 / 重复用户名 / 重复邮箱 / 重复学号 / 教师与超管不传学号
- GET /api/users 鉴权（无 Token / 学生 / 教师 / 超管）与敏感字段检查
- 修改用户角色通过单个 PATCH 完成，且角色-学号联动正确
"""
import pytest


@pytest.fixture()
def superadmin(user_factory):
    return user_factory("admin_root", "superadmin")


def _payload(**overrides) -> dict:
    base = {
        "username": "stu_new",
        "email": "stu_new@school.edu",
        "password": "123456",
        "name": "新学生",
        "role": "student",
        "studentId": "20240101",
        "status": "active",
    }
    base.update(overrides)
    return base


# ========== 创建用户：参数校验 ==========

@pytest.mark.parametrize(
    ("overrides", "msg_part"),
    [
        ({"studentId": None}, "学号"),               # 学生缺少学号
        ({"studentId": ""}, "学号"),
        ({"email": "not-an-email"}, "email"),        # 非法邮箱
        ({"password": "12345"}, "password"),         # 密码不足 6 位
        ({"username": "a"}, "username"),             # 用户名过短
        ({"username": "   "}, "username"),           # 用户名为空白
        ({"name": "  "}, "name"),                    # 姓名为空白
        ({"role": "monitor"}, "role"),               # 非法角色
        ({"status": "frozen"}, "status"),            # 非法状态
        ({"phone": "12345678900"}, "phone"),         # 手机号格式错误
        ({"phone": "21345678901"}, "phone"),         # 不符合 1[3-9] 开头
    ],
)
def test_create_user_validates_fields(client, superadmin, auth_header, overrides, msg_part):
    response = client.post(
        "/api/users", json=_payload(**overrides), headers=auth_header(superadmin),
    )

    assert response.status_code == 422
    assert msg_part in response.json()["message"]


def test_create_user_requires_name(client, superadmin, auth_header):
    """name 为必填，缺失时 422。"""
    payload = _payload()
    payload.pop("name")
    response = client.post("/api/users", json=payload, headers=auth_header(superadmin))

    assert response.status_code == 422
    assert "name" in response.json()["message"]


def test_create_user_rejects_empty_username(client, superadmin, auth_header):
    response = client.post(
        "/api/users", json=_payload(username=""), headers=auth_header(superadmin),
    )

    assert response.status_code == 422


# ========== 创建用户：唯一性 ==========

def test_create_user_rejects_duplicate_username(client, superadmin, auth_header):
    """重复用户名（与既有用户同名）→ 409。"""
    response = client.post(
        "/api/users", json=_payload(username="admin_root"), headers=auth_header(superadmin),
    )

    assert response.status_code == 409
    assert response.json()["code"] == 10009


def test_create_user_rejects_duplicate_email(client, superadmin, auth_header):
    response = client.post(
        "/api/users", json=_payload(email="admin_root@test.local"), headers=auth_header(superadmin),
    )

    assert response.status_code == 409
    assert response.json()["code"] == 10009


def test_create_user_rejects_duplicate_student_id(client, superadmin, auth_header):
    """student_id 按唯一处理：与其他学生学号重复 → 409。"""
    # 先创建一个带学号的学生
    first = client.post(
        "/api/users", json=_payload(), headers=auth_header(superadmin),
    )
    assert first.status_code == 200

    response = client.post(
        "/api/users",
        json=_payload(
            username="stu_dup", email="stu_dup@school.edu", studentId="20240101",
        ),
        headers=auth_header(superadmin),
    )

    assert response.status_code == 409
    assert response.json()["code"] == 10009


# ========== 创建用户：正常路径 ==========

def test_create_teacher_without_student_id(client, superadmin, auth_header):
    """教师不传学号 → 创建成功且 studentId 为空。"""
    response = client.post(
        "/api/users",
        json=_payload(
            username="tea_new", email="tea_new@school.edu",
            role="teacher", studentId=None, name="新教师",
        ),
        headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["role"] == "teacher"
    assert data["studentId"] is None


def test_create_superadmin_without_student_id(client, superadmin, auth_header):
    """超级管理员不传学号 → 创建成功。"""
    response = client.post(
        "/api/users",
        json=_payload(
            username="admin_new", email="admin_new@school.edu",
            role="superadmin", studentId=None, name="新管理员",
        ),
        headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "superadmin"


def test_create_user_clears_student_id_for_non_student(client, superadmin, auth_header):
    """非学生角色即使传了学号也会被清除。"""
    response = client.post(
        "/api/users",
        json=_payload(username="tea_x", email="tea_x@school.edu", role="teacher", studentId="20240102"),
        headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    assert response.json()["data"]["studentId"] is None


def test_create_student_success(client, superadmin, auth_header):
    response = client.post(
        "/api/users", json=_payload(), headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == "stu_new"
    assert data["studentId"] == "20240101"
    # 响应不得包含密码等敏感字段
    assert "password" not in data


def test_batch_import_still_works_for_teacher(client, teacher, auth_header):
    """删除注册功能不影响教师批量导入。"""
    response = client.post(
        "/api/users/batch-import",
        json=[{"name": "导入学生", "studentId": "20240202"}],
        headers=auth_header(teacher),
    )

    assert response.status_code == 200
    assert response.json()["data"]["successCount"] == 1


# ========== GET /api/users 鉴权 ==========

def test_get_users_requires_token(client):
    response = client.get("/api/users")

    assert response.status_code == 401


def test_get_users_forbidden_for_student(client, student, auth_header):
    response = client.get("/api/users", headers=auth_header(student))

    assert response.status_code == 403


def test_get_users_forbidden_for_teacher(client, teacher, auth_header):
    """当前用户列表仅超级管理员的用户管理/系统班级页使用。"""
    response = client.get("/api/users", headers=auth_header(teacher))

    assert response.status_code == 403


def test_get_users_allowed_for_superadmin(client, superadmin, auth_header):
    response = client.get("/api/users", headers=auth_header(superadmin))

    assert response.status_code == 200
    data = response.json()["data"]
    assert "items" in data
    for item in data["items"]:
        assert "password" not in item
        assert "token" not in item


def test_get_users_filters_by_status(client, superadmin, auth_header):
    """状态筛选参数此前后端未实现（前端一直在传），现在应生效。"""
    response = client.get(
        "/api/users", params={"status": "locked"}, headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    for item in response.json()["data"]["items"]:
        assert item["status"] == "locked"


# ========== 修改用户（单角色设计：role 随 PATCH 生效） ==========

def test_update_user_role_via_single_patch(client, superadmin, auth_header, student):
    """修改角色只需一个 PATCH：student → teacher，学号被清空。"""
    response = client.patch(
        f"/api/users/{student.id}",
        json={"role": "teacher"},
        headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["role"] == "teacher"
    assert data["studentId"] is None


def test_update_user_role_to_student_requires_student_id(client, superadmin, auth_header, teacher):
    """教师改学生必须补学号。"""
    response = client.patch(
        f"/api/users/{teacher.id}",
        json={"role": "student"},
        headers=auth_header(superadmin),
    )

    assert response.status_code == 400
    assert response.json()["code"] == 10011


def test_update_user_rejects_duplicate_email(client, superadmin, auth_header, teacher, student):
    response = client.patch(
        f"/api/users/{teacher.id}",
        json={"email": student.email},
        headers=auth_header(superadmin),
    )

    assert response.status_code == 409
    assert response.json()["code"] == 10009


def test_update_user_rejects_duplicate_student_id(client, superadmin, auth_header, teacher):
    # 先创建一个带学号的学生，再把教师改成同 学号 的学生 → 409
    created = client.post(
        "/api/users", json=_payload(), headers=auth_header(superadmin),
    )
    assert created.status_code == 200

    response = client.patch(
        f"/api/users/{teacher.id}",
        json={"role": "student", "studentId": "20240101"},
        headers=auth_header(superadmin),
    )

    assert response.status_code == 409


def test_update_user_accepts_locked_status(client, superadmin, auth_header, student):
    """状态枚举包含 locked（前后端统一）。"""
    response = client.patch(
        f"/api/users/{student.id}",
        json={"status": "locked"},
        headers=auth_header(superadmin),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "locked"


def test_create_user_forbidden_for_teacher(client, teacher, auth_header):
    """新增用户仅超级管理员。"""
    response = client.post(
        "/api/users", json=_payload(), headers=auth_header(teacher),
    )

    assert response.status_code == 403
