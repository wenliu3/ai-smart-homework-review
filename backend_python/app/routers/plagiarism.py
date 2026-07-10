"""临时文档查重路由 — 不依赖学生提交记录，上传文件直接查重

支持双维度查重:
  1. 文本维度 (text.py): N-gram + 词级 TF-IDF，检测文字照抄/改写
  2. 图片维度 (image.py): 感知哈希(aHash+dHash)，检测截图复制粘贴

支持任务书/模板过滤:
  老师可额外上传一份 template_file（任务书/起始代码模板），
  比对前自动从每份提交里剔除模板内容（文本和图片两个维度分别剔除）。
"""
import uuid
import time
import io
import os
import tempfile
from collections import OrderedDict
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from ..deps import get_current_user, require_roles
from ..models import User
from ..plagiarism import (
    run_full_check,
    extract_all_from_file,
    valid_char_count,
)
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
    expired = [k for k, v in _CACHE.items() if now - v["timestamp"] > _CACHE_TTL]
    for k in expired:
        del _CACHE[k]
    while len(_CACHE) > _CACHE_MAX_SIZE:
        _CACHE.popitem(last=False)





@router.post("/plagiarism/adhoc-check")
async def adhoc_check(
    files: List[UploadFile] = File(...),
    template_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_roles("superadmin", "teacher")),
):
    """临时查重 — 上传多个 docx/txt/pdf 文件，内存处理，不落盘不写库

    可选参数 template_file: 上传一份任务书/起始代码模板，比对前自动剔除模板内容。
    同时进行文本、代码、图片三个维度查重，合并返回结果。
    """
    _clean_cache()

    if len(files) < 2:
        raise BadRequestException(10011, "至少需要2份文件才能进行查重比对")

    # ---- 提取模板的文本和图片 ----
    template_text = ""
    template_images = []
    if template_file:
        try:
            tf_ext = "." + (template_file.filename or "").rsplit(".", 1)[-1].lower() if "." in (template_file.filename or "") else ""
            tf_bytes = await template_file.read()
            tf_tmp = os.path.join(tempfile.gettempdir(), f"plagiarism_template_{uuid.uuid4().hex}{tf_ext}")
            with open(tf_tmp, "wb") as tmp:
                tmp.write(tf_bytes)
            template_text, template_images = extract_all_from_file(tf_tmp, tf_ext)
            os.remove(tf_tmp)
        except Exception:
            pass

    # ---- 提取每份提交的文本和图片 ----
    student_data = []
    image_data = []
    skipped = []

    for f in files:
        filename = f.filename or "unknown.docx"
        try:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            content_bytes = await f.read()
            tmp_path = os.path.join(tempfile.gettempdir(), f"plagiarism_tmp_{uuid.uuid4().hex}{ext}")
            with open(tmp_path, "wb") as tmp:
                tmp.write(content_bytes)
            full_text, images = extract_all_from_file(tmp_path, ext)
            os.remove(tmp_path)

            # 尝试从文件名解析 姓名_学号
            base = filename.rsplit(".", 1)[0]
            parts = base.split("_")
            name = parts[0].strip() if len(parts) >= 1 else base
            stu_id = parts[1].strip() if len(parts) >= 2 else ""

            # 文本查重数据
            if valid_char_count(full_text) < 40:
                skipped.append({"fileName": filename, "reason": "有效字符数过少，可能是空白文件"})
            else:
                student_data.append({
                    "id": len(student_data) + 1,
                    "studentName": name,
                    "studentNumber": stu_id,
                    "content": full_text,
                })

            # 图片查重数据
            if images:
                image_data.append({
                    "id": len(image_data) + 1,
                    "studentName": name,
                    "studentNumber": stu_id,
                    "images": images,
                })

        except Exception as e:
            skipped.append({"fileName": filename, "reason": f"解析失败: {e}"})

    # ---- 双维度查重 + 合并 ----
    result = run_full_check(
        text_submissions=student_data,
        image_submissions=image_data if len(image_data) >= 2 else None,
        template_text=template_text or None,
        template_images=template_images or None,
        skipped=skipped,
    )

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
    has_image = result.get("imageResult") is not None

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = "查重结果"

    headers = ["排名", "姓名", "学号",
                "片段重合度(%)", "主题相似度(%)", "综合重复率(%)", "文本判定"]
    if has_image:
        headers += ["图片重合度(%)", "疑似复制图片数", "图片判定"]
    headers += ["最相似对象", "对方学号", "疑似抄袭原因"]

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")

    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    for idx, r in enumerate(results, 1):
        row_data = [
            idx,
            r["studentName"],
            r["studentNumber"],
            r.get("phraseRate") if r.get("phraseRate") is not None else "-",
            r.get("topicRate") if r.get("topicRate") is not None else "-",
            r.get("rate") if r.get("rate") is not None else "-",
            r.get("status", "-"),
        ]
        if has_image:
            row_data += [
                r.get("imageRate") if r.get("imageRate") is not None else "-",
                r.get("matchedImageCount", 0),
                r.get("imageStatus", "-"),
            ]
        row_data += [
            r.get("matchName", "-"),
            r.get("matchId", "-"),
            r.get("suspectReason", "") or "合格",
        ]
        ws.append(row_data)
        if r.get("suspectReason"):
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
