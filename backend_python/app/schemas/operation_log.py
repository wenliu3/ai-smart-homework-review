"""操作日志 schemas"""
from pydantic import BaseModel


class OperationLogQuery(BaseModel):
    """操作日志查询参数"""
    page: int = 1
    pageSize: int = 20
    operator: str | None = None
    action: str | None = None
    module: str | None = None
    keyword: str | None = None
    startDate: str | None = None
    endDate: str | None = None
