"""操作日志路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import User
from ..core.response import ok
from ..crud import operation_log as log_crud

router = APIRouter()


@router.get("/admin/logs")
def get_logs(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    operator: str | None = Query(None),
    action: str | None = Query(None),
    module: str | None = Query(None),
    keyword: str | None = Query(None),
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    current_user: User = Depends(require_roles("superadmin")),
    db: Session = Depends(get_db),
):
    """分页查询操作日志 — 限超级管理员"""
    params = {
        "page": page, "pageSize": pageSize,
        "operator": operator, "action": action, "module": module,
        "keyword": keyword, "startDate": startDate, "endDate": endDate,
    }
    return ok(log_crud.get_list(db, params))
