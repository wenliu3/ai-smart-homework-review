"""导入模板下载路由 — 为批量导入功能提供 Excel 模板"""
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from ..deps import require_roles
from ..models import User
from ..core.exceptions import NotFoundException

router = APIRouter()

# 模板类型 → 列头（列头与前端 ImportUsersDialog 解析逻辑严格一致）
TEMPLATE_COLUMNS = {
    "user-import": ["用户名", "姓名", "邮箱", "学号", "手机号"],
}


@router.get("/v1/templates/{template_type}")
def download_template(template_type: str, current_user: User = Depends(require_roles("teacher", "superadmin"))):
    """下载批量导入模板（教师/超级管理员）— 目前支持 user-import 用户导入模板"""
    columns = TEMPLATE_COLUMNS.get(template_type)
    if not columns:
        raise NotFoundException(10015, f"模板类型不存在: {template_type}")

    wb = Workbook()
    ws = wb.active
    ws.title = "导入数据"
    ws.append(columns)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"{template_type}_template.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
