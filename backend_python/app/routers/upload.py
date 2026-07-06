"""文件上传 / 下载 / 预览路由"""
import os
import time
import random
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from ..deps import get_current_user
from ..core.response import ok
from ..core.exceptions import NotFoundException, BadRequestException
from ..core.file_parser import extract_file_text
from ..config import settings
from ..models import User

router = APIRouter()

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".txt"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB，防止单次读取大文件导致 OOM
MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}


@router.post("/upload/files")
async def upload_files(files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user)):
    """上传文件 — 支持多文件，自动提取文本内容，返回文件URL和文本"""
    if not files:
        return ok({"files": []})
    upload_dir = settings.upload_path
    attachments = []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXTS:
            continue
        content = await f.read()
        # 校验文件大小，防止超大文件导致内存溢出
        if len(content) > MAX_FILE_SIZE:
            raise BadRequestException(10011, f"文件「{f.filename}」超过大小限制({MAX_FILE_SIZE // 1024 // 1024}MB)")
        timestamp = int(time.time() * 1000)
        random_num = random.randint(0, 10**9 - 1)
        saved_name = f"{timestamp}-{random_num}{ext}"
        file_path = upload_dir / saved_name
        file_path.write_bytes(content)

        text_content = extract_file_text(str(file_path), ext)
        attachments.append({
            "fileName": f.filename,
            "fileUrl": f"/uploads/{saved_name}",
            "fileSize": len(content),
            "fileType": f.content_type or MIME_MAP.get(ext, "application/octet-stream"),
            "textContent": text_content,
        })
    return ok({"files": attachments, "uploadedCount": len(attachments)})


@router.get("/upload/download/{filename}")
def download_file(filename: str, current_user: User = Depends(get_current_user)):
    """下载文件 — 图片/PDF/TXT 内联显示，其他类型附件下载"""
    file_path = settings.upload_path / filename
    if not file_path.exists():
        return JSONResponse({"code": 404, "message": "文件不存在"}, status_code=404)
    ext = os.path.splitext(filename)[1].lower()
    media_type = MIME_MAP.get(ext, "application/octet-stream")
    disposition = "inline" if ext in (".pdf", ".txt") else "attachment"
    return FileResponse(
        path=str(file_path), media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/upload/preview/{filename}")
async def preview_file(filename: str, current_user: User = Depends(get_current_user)):
    """在线预览文件 — 图片/PDF/TXT 直接返回，docx 提取文本转HTML"""
    file_path = settings.upload_path / filename
    if not file_path.exists():
        return JSONResponse({"code": 404, "message": "文件不存在"}, status_code=404)
    ext = os.path.splitext(filename)[1].lower()

    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".txt"):
        return FileResponse(path=str(file_path), media_type=MIME_MAP.get(ext, "application/octet-stream"), headers={"Content-Disposition": "inline"})
    if ext == ".docx":
        try:
            text = extract_file_text(str(file_path), ext) or "文档内容为空."
            escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'><title>文件预览</title>"
                "<style>body{font-family:'Microsoft YaHei',sans-serif;padding:20px;line-height:1.8;white-space:pre-wrap;word-break:break-all}</style>"
                f"</head><body>{escaped}</body></html>"
            )
            return HTMLResponse(html)
        except Exception as e:
            return JSONResponse({"fileName": filename, "fileType": ext, "message": f"预览失败: {e}"})
    stat = file_path.stat()
    return ok({"fileName": filename, "fileSize": stat.st_size, "fileType": ext, "message": f"文件类型 {ext} 不支持在线预览，请下载查看"})
