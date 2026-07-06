"""统一响应格式: { code, data, message }"""
from typing import Any, Optional


def ok(data: Any = None, message: str = "操作成功") -> dict:
    return {"code": 200, "data": data, "message": message}


def error(code: int = 10000, message: str = "服务器内部错误") -> dict:
    return {"code": code, "message": message}
