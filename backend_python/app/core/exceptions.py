"""自定义业务异常 - 对齐 NestJS 的 HttpException 语义"""
from typing import Any, Optional


class BizException(Exception):
    """业务异常，携带 code 与 HTTP 状态码"""

    def __init__(self, code: int = 10000, message: str = "服务器内部错误", status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnauthorizedException(BizException):
    def __init__(self, code: int = 10002, message: str = "认证失败"):
        super().__init__(code, message, 401)


class ForbiddenException(BizException):
    def __init__(self, code: int = 10007, message: str = "权限不足"):
        super().__init__(code, message, 403)


class NotFoundException(BizException):
    def __init__(self, code: int = 10015, message: str = "资源不存在"):
        super().__init__(code, message, 404)


class BadRequestException(BizException):
    def __init__(self, code: int = 10011, message: str = "请求参数错误"):
        super().__init__(code, message, 400)


class ConflictException(BizException):
    def __init__(self, code: int = 10009, message: str = "资源冲突"):
        super().__init__(code, message, 409)
