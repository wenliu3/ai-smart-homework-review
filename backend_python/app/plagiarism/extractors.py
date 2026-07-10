"""从 docx / txt / pdf 中提取文本和图片的公共函数。

查重模块（text/image）只负责算相似度，不关心怎么从 docx 里挖数据，
职责更单一。以后要支持 PDF/其他格式，只用改这个文件。
"""
import os
import html
import logging
import pdfplumber
from docx import Document

logger = logging.getLogger(__name__)


# ===================== 全文文本提取 =====================

def extract_file_text(file_path: str, ext: str) -> str:
    """从 txt / pdf / docx 文件中提取纯文本"""
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
            return _extract_docx_text(Document(file_path))
    except Exception as e:
        logger.warning("提取失败 [%s]: %s: %s", ext, file_path, e)
    return ""


def _extract_docx_text(doc) -> str:
    """从已打开的 Document 对象提取全文文本（段落 + 表格 + 页眉页脚）"""
    parts = []

    # 1. 正文段落
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)

    # 2. 表格文本（实验报告等内容常在表格里）
    def _extract_table(table):
        for row in table.rows:
            row_texts = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    row_texts.append(cell_text)
                for nested_table in cell.tables:
                    _extract_table(nested_table)
            if row_texts:
                parts.append("\n".join(row_texts))

    for table in doc.tables:
        _extract_table(table)

    # 3. 页眉页脚
    for section in doc.sections:
        if section.header and section.header.paragraphs:
            for p in section.header.paragraphs:
                if p.text.strip():
                    parts.append(p.text)
        if section.footer and section.footer.paragraphs:
            for p in section.footer.paragraphs:
                if p.text.strip():
                    parts.append(p.text)

    return "\n".join(parts)


# ===================== 图片提取 =====================

def extract_images_from_docx(docx_path: str = None, doc=None) -> list:
    """返回该 docx 内所有内嵌图片的原始二进制内容列表。
    可传入已打开的 Document 对象(doc)以复用，避免同一份文件解析两次。"""
    if doc is None:
        doc = Document(docx_path)
    images = []
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                images.append(rel.target_part.blob)
            except Exception:
                continue
    return images


# ===================== 一次性提取文本+图片（复用 Document 对象） =====================

def extract_all_from_docx(file_path: str) -> tuple:
    """从 docx 中同时提取全文文本和内嵌图片，复用同一个 Document 对象。

    返回: (full_text, images)
      - full_text: 全文文本（段落 + 表格 + 页眉页脚）
      - images: docx 内所有内嵌图片的原始二进制内容列表 [bytes, ...]
    """
    try:
        doc = Document(file_path)
        full_text = _extract_docx_text(doc)
        images = extract_images_from_docx(doc=doc)
        return full_text, images
    except Exception as e:
        logger.warning("docx文本+图片提取失败: %s: %s", file_path, e)
        return "", []


def extract_all_from_file(tmp_path: str, ext: str) -> tuple:
    """通用入口：根据文件扩展名选择提取方式。
    对 .docx 使用 extract_all_from_docx 复用同一个 Document 对象；
    对其他格式用 extract_file_text 提取全文，图片为空列表。
    返回: (full_text, images)
    """
    if ext == ".docx":
        return extract_all_from_docx(tmp_path)
    else:
        full_text = extract_file_text(tmp_path, ext)
        return full_text, []


# ===================== docx → HTML（Word 视图） =====================

def docx_to_html(file_path: str) -> str:
    """用 mammoth 将 docx 转换为保留排版的 HTML（标题/表格/加粗/图片等）。
    mammoth 未安装或转换失败时回退为 <pre> 纯文本。"""
    try:
        import mammoth
        with open(file_path, "rb") as f:
            result = mammoth.convert_to_html(f)
            return result.value
    except Exception as e:
        logger.warning("mammoth 转换失败，回退纯文本: %s: %s", file_path, e)
        text = _extract_docx_text(Document(file_path))
        return "<pre>" + html.escape(text) + "</pre>"


def file_to_html(file_path: str, ext: str) -> str:
    """将任意附件文件转为 HTML（docx 用 mammoth，其他用 <pre> 纯文本）"""
    ext = (ext or "").lower()
    if not ext.startswith("."):
        ext = "." + ext
    if ext == ".docx":
        return docx_to_html(file_path)
    text = extract_file_text(file_path, ext)
    return "<pre>" + html.escape(text) + "</pre>" if text else ""
