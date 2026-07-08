"""Unit tests for app.core.response 统一响应格式."""
from app.core import response


class TestOk:
    def test_defaults(self):
        assert response.ok() == {"code": 200, "data": None, "message": "操作成功"}

    def test_with_data(self):
        assert response.ok({"id": 1}) == {
            "code": 200,
            "data": {"id": 1},
            "message": "操作成功",
        }

    def test_custom_message(self):
        out = response.ok([1, 2], message="查询成功")
        assert out == {"code": 200, "data": [1, 2], "message": "查询成功"}


class TestError:
    def test_defaults(self):
        assert response.error() == {"code": 10000, "message": "服务器内部错误"}

    def test_custom(self):
        assert response.error(404, "资源不存在") == {
            "code": 404,
            "message": "资源不存在",
        }

    def test_error_has_no_data_key(self):
        assert "data" not in response.error()
