"""操作日志 CRUD — 仅支持查询和写入，不支持修改/删除（日志不可篡改）"""
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.orm import Session
from ..models import OperationLog
from ..core.utils import camel_to_snake


def get_list(db: Session, params: dict) -> dict:
    """分页查询操作日志，支持按操作人/操作类型/模块/关键词/日期范围筛选"""
    query = db.query(OperationLog)

    # 筛选条件
    if params.get("operator"):
        query = query.filter(OperationLog.operator.like(f"%{params['operator']}%"))
    if params.get("action"):
        query = query.filter(OperationLog.action == params["action"])
    if params.get("module"):
        query = query.filter(OperationLog.module == params["module"])
    if params.get("keyword"):
        kw = f"%{params['keyword']}%"
        query = query.filter(
            (OperationLog.description.like(kw)) |
            (OperationLog.operator_name.like(kw))
        )
    if params.get("startDate"):
        try:
            start = datetime.fromisoformat(params["startDate"])
            query = query.filter(OperationLog.created_at >= start)
        except ValueError:
            pass
    if params.get("endDate"):
        try:
            end = datetime.fromisoformat(params["endDate"])
            query = query.filter(OperationLog.created_at <= end)
        except ValueError:
            pass

    total = query.count()
    page = max(1, int(params.get("page", 1)))
    page_size = max(1, min(100, int(params.get("pageSize", 20))))
    items = query.order_by(desc(OperationLog.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [item.to_dict() for item in items],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def create_log(
    db: Session,
    operator: str,
    operator_name: str,
    action: str,
    module: str,
    description: str,
    ip: str = "",
    method: str = "",
    endpoint: str = "",
    status_code: int = 200,
) -> dict:
    """写入一条操作日志"""
    log = OperationLog(
        operator=operator,
        operator_name=operator_name,
        action=action,
        module=module,
        description=description,
        ip=ip,
        method=method,
        endpoint=endpoint,
        status_code=status_code,
    )
    db.add(log)
    db.commit()
    return log.to_dict()
