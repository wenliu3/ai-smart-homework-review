"""Unit tests for app.core.exceptions 业务异常."""
import pytest

from app.core import exceptions as exc


class TestBizException:
    def test_defaults(self):
        e = exc.BizException()
        assert e.code == 10000
        assert e.message == "服务器内部错误"
        assert e.status_code == 400
        assert str(e) == "服务器内部错误"

    def test_custom_values(self):
        e = exc.BizException(code=123, message="boom", status_code=418)
        assert (e.code, e.message, e.status_code) == (123, "boom", 418)

    def test_is_exception(self):
        with pytest.raises(exc.BizException):
            raise exc.BizException()


@pytest.mark.parametrize(
    "cls,code,status,message",
    [
        (exc.UnauthorizedException, 10002, 401, "认证失败"),
        (exc.ForbiddenException, 10007, 403, "权限不足"),
        (exc.NotFoundException, 10015, 404, "资源不存在"),
        (exc.BadRequestException, 10011, 400, "请求参数错误"),
        (exc.ConflictException, 10009, 409, "资源冲突"),
    ],
)
class TestSubclasses:
    def test_default_attributes(self, cls, code, status, message):
        e = cls()
        assert e.code == code
        assert e.status_code == status
        assert e.message == message

    def test_subclass_of_biz(self, cls, code, status, message):
        assert isinstance(cls(), exc.BizException)

    def test_custom_message(self, cls, code, status, message):
        e = cls(message="自定义")
        assert e.message == "自定义"
        assert e.status_code == status
