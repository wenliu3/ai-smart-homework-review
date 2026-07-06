"""通用响应与分页 schemas"""
from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel):
    """统一响应格式"""
    code: int = 200
    data: Any = None
    message: str = "操作成功"


class ErrorResponse(BaseModel):
    code: int
    message: str


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
