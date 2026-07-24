"""测试基础设施冒烟：夹具可用、应用可导入、测试库隔离生效。"""
from app.models import User


def test_db_fixture_creates_user(db, user_factory):
    user = user_factory("smoke_teacher", "teacher")
    assert user.id is not None
    assert db.query(User).filter_by(username="smoke_teacher").count() == 1


def test_client_serves_api_docs(client):
    resp = client.get("/api/docs")
    assert resp.status_code == 200


def test_db_is_clean_between_tests(db):
    assert db.query(User).count() == 0
