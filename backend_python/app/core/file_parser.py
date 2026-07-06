"""文档文本提取(txt / pdf / docx)"""
import os
import logging
import pdfplumber
from docx import Document

logger = logging.getLogger(__name__)


def extract_file_text(file_path: str, ext: str) -> str:
    ext = (ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext
    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        if ext == ".pdf":
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join((p.extract_text() or "") for p in pdf.pages)
                return text
        if ext == ".docx":
            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text
    except Exception as e:
        logger.warning("提取失败 [%s]: %s: %s", ext, file_path, e)
    return ""
