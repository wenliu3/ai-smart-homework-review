"""统一账号登录契约。"""
import pytest

from app.core.security import hash_password
from app.models import User


@pytest.fixture()
def login_teacher(db):
    user = User(
        username="login_teacher",
        email="login_teacher@test.local",
        student_id="2024999",
        password=hash_password("test-password"),
        name="Login Teacher",
        role="teacher",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.parametrize(
    "account",
    ["login_teacher", "login_teacher@test.local", "2024999"],
)
def test_login_accepts_username_email_or_student_id(client, login_teacher, account):
    response = client.post(
        "/api/v1/auth/login",
        json={"usernameOrEmailOrStudentId": account, "password": "test-password"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 200
    assert body["data"]["user"]["id"] == str(login_teacher.id)


@pytest.mark.parametrize(
    ("account", "password"),
    [
        ("missing_login_teacher", "test-password"),
        ("login_teacher", "wrong-password"),
    ],
)
def test_login_rejects_unknown_account_or_wrong_password(
    client, login_teacher, account, password,
):
    response = client.post(
        "/api/v1/auth/login",
        json={"usernameOrEmailOrStudentId": account, "password": password},
    )

    body = response.json()
    assert response.status_code == 401
    assert body["message"] == "账号或密码错误"
