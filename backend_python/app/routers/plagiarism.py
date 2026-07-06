"""临时文档查重路由 — 不依赖学生提交记录，上传文件直接查重"""
import uuid
import time
import io
from collections import OrderedDict
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from ..deps import get_current_user, require_roles
from ..models import User
from ..core.file_parser import extract_file_text
from ..core.plagiarism import run_plagiarism_check, valid_char_count
from ..core.exceptions import BadRequestException
from ..core.response import ok

router = APIRouter()

# 内存缓存: OrderedDict 实现 LRU，限制最大条目数防止内存无限膨胀
_CACHE: OrderedDict = OrderedDict()
_CACHE_MAX_SIZE = 100  # 缓存最大条目数
_CACHE_TTL = 1800  # 30分钟


def _clean_cache():
    """清理过期的缓存记录，并淘汰超限的最旧条目（LRU）"""
    now = time.time()
    # 清理过期记录
    expired = [k for k, v in _CACHE.items() if now - v["timestamp"] > _CACHE_TTL]
    for k in expired:
        del _CACHE[k]
    # 如果仍超限，淘汰最旧的条目（LRU）
    while len(_CACHE) > _CACHE_MAX_SIZE:
        _CACHE.popitem(last=False)


@router.post("/plagiarism/adhoc-check")
async def adhoc_check(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_roles("superadmin", "teacher")),
):
    """临时查重 — 上传多个 docx/txt 文件，内存处理，不落盘不写库"""
    _clean_cache()

    if len(files) < 2:
        raise BadRequestException(10011, "至少需要2份文件才能进行查重比对")

    student_data = []
    skipped = []

    for f in files:
        filename = f.filename or "unknown.docx"
        try:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            content_bytes = await f.read()
            # 直接在内存中提取文本，不写磁盘
            import tempfile, os
            tmp_path = os.path.join(tempfile.gettempdir(), f"plagiarism_tmp_{uuid.uuid4().hex}{ext}")
            with open(tmp_path, "wb") as tmp:
                tmp.write(content_bytes)
            text = extract_file_text(tmp_path, ext)
            os.remove(tmp_path)  # 立即删除临时文件

            if valid_char_count(text) < 40:
                skipped.append({"fileName": filename, "reason": "有效字符数过少，可能是空白文件"})
                continue

            # 尝试从文件名解析 姓名_学号
            base = filename.rsplit(".", 1)[0]
            parts = base.split("_")
            name = parts[0].strip() if len(parts) >= 1 else base
            stu_id = parts[1].strip() if len(parts) >= 2 else ""

            student_data.append({
                "id": len(student_data) + 1,
                "studentName": name,
                "studentNumber": stu_id,
                "content": text,
            })
        except Exception as e:
            skipped.append({"fileName": filename, "reason": f"解析失败: {e}"})

    if len(student_data) < 2:
        raise BadRequestException(10011, f"有效文件不足2份(跳过{len(skipped)}份)，无法查重")

    result = run_plagiarism_check(student_data)
    result["skipped"] = skipped + result.get("skipped", [])

    # 存入内存缓存，供下载报告用
    check_id = str(uuid.uuid4())
    _CACHE[check_id] = {"result": result, "timestamp": time.time()}

    return ok({"checkId": check_id, **result})


@router.get("/plagiarism/{check_id}/report")
def download_report(
    check_id: str,
    current_user: User = Depends(require_roles("superadmin", "teacher")),
):
    """下载查重报告 Excel — 从内存缓存取结果，生成后流式返回"""
    _clean_cache()

    cached = _CACHE.get(check_id)
    if not cached:
        raise BadRequestException(10011, "查重结果已过期(超过30分钟)，请重新查重")

    result = cached["result"]
    results = result.get("results", [])

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = "查重结果"

    headers = ["排名", "姓名", "学号", "片段重合度(%)", "主题相似度(%)", "综合重复率(%)", "最相似对象", "对方学号", "判定结果"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")

    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    for idx, r in enumerate(results, 1):
        ws.append([idx, r["studentName"], r["studentNumber"], r["phraseRate"],
                    r["topicRate"], r["rate"], r["matchName"], r["matchId"], r["status"]])
        if r["status"] != "合格":
            for cell in ws[ws.max_row]:
                cell.fill = red_fill

    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col) + 4
        ws.column_dimensions[col[0].column_letter].width = max_len

    # 输出到内存流
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"查重报告_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
