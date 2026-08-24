"""已移除端点的回归测试：注册与旧版认证端点必须返回 404。

业务原则：系统不开放自行注册，用户只能由超级管理员新增或批量导入，
不能通过直连原注册接口绕过前端创建账号。
"""
import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/register",
        "/api/auth/register",
        "/api/auth/login",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
    ],
)
def test_removed_auth_endpoints_return_404(client, path):
    response = client.post(path, json={})

    assert response.status_code == 404, f"{path} 应已下线（404）"


def test_login_still_works_after_cleanup(client, teacher):
    """清理注册后，正式登录接口必须保持可用。"""
    response = client.post(
        "/api/v1/auth/login",
        json={"usernameOrEmailOrStudentId": "t_alice", "password": "test-password"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == 200
