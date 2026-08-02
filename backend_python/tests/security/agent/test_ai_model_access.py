"""/admin/ai-models 全端点的角色边界与密钥脱敏测试。

- 管理端点仅限超级管理员，教师/学生一律 403。
- /active 对教师开放（AI 规则表单的模型下拉框），但只返回非敏感字段。
- 超管响应中的 apiKey/accessKey/secretKey 一律脱敏。
- 更新配置时回传掩码值或空值不得覆盖库中真实密钥。
"""
import pytest

from app.models import AiModel

BASE = "/api/admin/ai-models"

PROTECTED_REQUESTS = [
    ("GET", BASE),
    ("POST", f"{BASE}/initialize"),
    ("GET", f"{BASE}/deepseek-chat"),
    ("PUT", f"{BASE}/deepseek-chat"),
    ("POST", f"{BASE}/deepseek-chat/default"),
    ("GET", f"{BASE}/deepseek-chat/balance"),
    ("POST", f"{BASE}/deepseek-chat/test"),
    ("GET", f"{BASE}/deepseek-chat/stats"),
    ("GET", f"{BASE}/grading-structurer/config"),
    ("PUT", f"{BASE}/grading-structurer/config"),
]


@pytest.fixture()
def superadmin(user_factory):
    return user_factory("admin_root", "superadmin")


@pytest.mark.parametrize("method,url", PROTECTED_REQUESTS)
def test_teacher_and_student_get_403_on_admin_model_endpoints(
    client, teacher, student, auth_header, ai_model_factory, method, url,
):
    ai_model_factory()
    for user in (teacher, student):
        resp = client.request(method, url, headers=auth_header(user), json={})
        assert resp.status_code == 403, f"{user.role} {method} {url} 应返回 403"


def test_student_cannot_read_active_models(
    client, student, auth_header, ai_model_factory,
):
    ai_model_factory()
    resp = client.get(f"{BASE}/active", headers=auth_header(student))
    assert resp.status_code == 403


def test_teacher_active_models_contain_no_secrets(
    client, teacher, auth_header, ai_model_factory,
):
    ai_model_factory(api_key="sk-live-secret-key-123456")
    resp = client.get(f"{BASE}/active", headers=auth_header(teacher))

    assert resp.status_code == 200
    items = resp.json()["data"]
    assert items and items[0]["code"] == "deepseek-chat"
    banned = {"apiKey", "accessKey", "secretKey", "baseUrl"}
    for item in items:
        assert not (set(item) & banned)
    assert "sk-live-secret-key-123456" not in resp.text


def test_superadmin_list_masks_all_secrets(
    client, superadmin, auth_header, ai_model_factory, db,
):
    model = ai_model_factory(api_key="sk-live-secret-key-123456")
    model.access_key = "access-secret-123456"
    model.secret_key = "secret-secret-123456"
    db.commit()

    resp = client.get(BASE, headers=auth_header(superadmin))

    assert resp.status_code == 200
    assert "sk-live-secret-key-123456" not in resp.text
    assert "access-secret-123456" not in resp.text
    assert "secret-secret-123456" not in resp.text
    item = resp.json()["data"]["models"][0]
    assert item["apiKey"] == "sk-l****3456"


def test_superadmin_detail_masks_secret(
    client, superadmin, auth_header, ai_model_factory,
):
    ai_model_factory(api_key="sk-live-secret-key-123456")
    resp = client.get(f"{BASE}/deepseek-chat", headers=auth_header(superadmin))

    assert resp.status_code == 200
    assert resp.json()["data"]["apiKey"] == "sk-l****3456"
    assert "sk-live-secret-key-123456" not in resp.text


def test_update_config_ignores_masked_or_empty_api_key(
    client, superadmin, auth_header, ai_model_factory, db,
):
    ai_model_factory(api_key="sk-live-secret-key-123456")

    masked = client.put(
        f"{BASE}/deepseek-chat",
        headers=auth_header(superadmin),
        json={"apiKey": "sk-l****3456", "status": "inactive"},
    )
    assert masked.status_code == 200
    db.expire_all()
    stored = db.query(AiModel).filter(AiModel.code == "deepseek-chat").one()
    assert stored.api_key == "sk-live-secret-key-123456"  # 掩码值未入库
    assert stored.status == "inactive"  # 非敏感字段正常更新

    empty = client.put(
        f"{BASE}/deepseek-chat",
        headers=auth_header(superadmin),
        json={"apiKey": ""},
    )
    assert empty.status_code == 200
    db.expire_all()
    stored = db.query(AiModel).filter(AiModel.code == "deepseek-chat").one()
    assert stored.api_key == "sk-live-secret-key-123456"


def test_update_config_accepts_new_real_api_key(
    client, superadmin, auth_header, ai_model_factory, db,
):
    ai_model_factory(api_key="sk-old-key-0123456789")
    resp = client.put(
        f"{BASE}/deepseek-chat",
        headers=auth_header(superadmin),
        json={"apiKey": "sk-new-key-abcdef123456"},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["apiKey"] == "sk-n****3456"
    db.expire_all()
    stored = db.query(AiModel).filter(AiModel.code == "deepseek-chat").one()
    assert stored.api_key == "sk-new-key-abcdef123456"


def test_superadmin_grading_structurer_config_binding_and_mask(
    client, superadmin, auth_header, ai_model_factory,
):
    """超管可读写独立结构化绑定；响应中的 apiKey 必须脱敏。"""
    ai_model_factory(api_key="sk-live-secret-key-123456")

    put = client.put(
        f"{BASE}/grading-structurer/config",
        headers=auth_header(superadmin),
        json={"enabled": True, "modelCode": "deepseek-chat"},
    )
    assert put.status_code == 200
    assert put.json()["data"]["enabled"] is True
    assert put.json()["data"]["modelCode"] == "deepseek-chat"
    assert "sk-live-secret-key-123456" not in put.text

    get = client.get(
        f"{BASE}/grading-structurer/config",
        headers=auth_header(superadmin),
    )
    assert get.status_code == 200
    data = get.json()["data"]
    assert data["enabled"] is True
    assert data["modelCode"] == "deepseek-chat"
    assert data["model"]["apiKey"] == "sk-l****3456"
    assert "sk-live-secret-key-123456" not in get.text


def test_superadmin_grading_structurer_config_can_disable(
    client, superadmin, auth_header, ai_model_factory,
):
    ai_model_factory(api_key="sk-live-secret-key-123456")
    client.put(
        f"{BASE}/grading-structurer/config",
        headers=auth_header(superadmin),
        json={"enabled": True, "modelCode": "deepseek-chat"},
    )
    resp = client.put(
        f"{BASE}/grading-structurer/config",
        headers=auth_header(superadmin),
        json={"enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["enabled"] is False
    assert data["modelCode"] is None
    assert data["model"] is None
