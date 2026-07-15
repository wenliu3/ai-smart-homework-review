"""提交 CRUD + AI 批改触发"""
import os
import re
import base64
import logging
import httpx
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import User, Assignment, Submission, AiModel
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.utils import now
from ..plagiarism.extractors import extract_file_text, extract_all_from_docx, extract_all_from_file
from ..plagiarism import get_word_tokens
from ..config import settings

logger = logging.getLogger(__name__)


def _delete_attachment_files(attachments: list):
    """删除附件对应的磁盘文件"""
    upload_dir = str(settings.upload_path)
    for att in (attachments or []):
        file_url = att.get("fileUrl", "")
        filename = file_url.replace("/uploads/", "")
        if filename:
            file_path = os.path.join(upload_dir, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning("删除附件文件失败: %s: %s", file_path, e)


def _max_score(assignment: Assignment) -> int:
    """获取作业的满分值(从 aiRule.maxScore 读取，默认 100)"""
    if assignment.ai_rule and isinstance(assignment.ai_rule, dict):
        return assignment.ai_rule.get("maxScore", 100)
    return 100


def _to100(score, max_score):
    """将原始分数换算为百分制"""
    if score is None:
        return None
    return round((score / max_score) * 100) if max_score > 0 else score


def submit(db: Session, student_id: int, data: dict) -> dict:
    """学生提交作业 — 若已有提交则更新(允许重复提交)，草稿不触发 AI 批改"""
    assignment_id = data.get("assignmentId")
    assignment = db.query(Assignment).filter(Assignment.id == int(assignment_id)).first()
    if not assignment:
        raise NotFoundException(10015, "作业不存在")
    if assignment.status != "published":
        raise BadRequestException(10011, "作业不可提交")
    is_draft = data.get("isDraft", False)
    if not is_draft and assignment.end_date and now() > assignment.end_date:
        raise BadRequestException(10011, "作业已截止，无法提交")

    attachments = data.get("attachments", []) or []
    content = data.get("content", "")
    # 重新从文件提取文本，计算字数并更新 textContent
    upload_dir = str(settings.upload_path)
    word_count = 0
    # 统计词数（jieba 分词后的词数，非字符数）
    if content:
        text_content = re.sub(r"<[^>]*>", "", content)
        word_count += len(get_word_tokens(text_content))
    for att in attachments:
        file_url = att.get("fileUrl", "")
        filename = file_url.replace("/uploads/", "")
        if filename:
            file_path = os.path.join(upload_dir, filename)
            ext = os.path.splitext(att.get("fileName", ""))[1].lower()
            text = extract_file_text(file_path, ext)
            if text:
                att["textContent"] = text
                word_count += len(get_word_tokens(text))
    submission = db.query(Submission).filter(
        Submission.assignment_id == assignment.id, Submission.student_id == student_id
    ).first()

    if submission:
        submission.content = content
        submission.attachments = attachments
        submission.word_count = word_count
        submission.is_draft = is_draft
        submission.status = "draft" if is_draft else "submitted"
        submission.submission_count = (submission.submission_count or 1) + 1
        if not is_draft:
            submission.submitted_at = now()
            submission.ai_score = None
            submission.ai_review_content = None
    else:
        submission = Submission(
            assignment_id=assignment.id, student_id=student_id,
            class_id=int(data.get("classId")), content=content, attachments=attachments, word_count=word_count,
            is_draft=is_draft, status="draft" if is_draft else "submitted",
            submitted_at=None if is_draft else now(), submission_count=1,
        )
        db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def get_my_submission(db: Session, assignment_id: int, student_id: int) -> dict:
    """学生查看自己的提交详情 — 含作业信息、提交内容、AI批改结果、教师批改结果"""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise NotFoundException(10015, "作业不存在")
    submission = db.query(Submission).filter(
        Submission.assignment_id == assignment_id, Submission.student_id == student_id
    ).first()
    max_score = _max_score(assignment)

    result = {
        "assignment": {
            "id": str(assignment.id), "title": assignment.title, "description": assignment.description,
            "dueDate": assignment.end_date.isoformat() if assignment.end_date else None,
            "maxScore": 100, "rawMaxScore": max_score, "teacherName": assignment.teacher_name,
            "aiRule": assignment.ai_rule, "status": assignment.status,
        },
        "submission": None, "aiReview": None, "teacherReview": None,
    }
    if submission:
        result["submission"] = {
            "id": str(submission.id),
            "content": submission.content or "",
            "attachments": submission.attachments, "wordCount": submission.word_count or 0,
            "status": submission.status,
            "submittedAt": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "updatedAt": submission.updated_at.isoformat() if submission.updated_at else None,
            "createdAt": submission.created_at.isoformat() if submission.created_at else None,
            "isDraft": submission.is_draft, "submissionCount": submission.submission_count,
        }
        if submission.ai_score is not None:
            result["aiReview"] = {
                "content": submission.ai_review_content or "",
                "score": _to100(submission.ai_score, max_score),
                "rawScore": submission.ai_score, "rawMaxScore": max_score,
                "reviewedAt": submission.updated_at.isoformat() if submission.updated_at else None,
            }
        if submission.teacher_score is not None:
            result["teacherReview"] = {
                "content": submission.teacher_review_content or "",
                "score": _to100(submission.teacher_score, max_score),
                "rawScore": submission.teacher_score, "rawMaxScore": max_score,
                "reviewedAt": submission.teacher_reviewed_at.isoformat() if submission.teacher_reviewed_at else None,
            }
    return result


def delete_submission(db: Session, submission_id: int, student_id: int) -> dict:
    """学生删除自己的草稿提交 — 只能删除 draft 状态"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise NotFoundException(10015, "提交记录不存在")
    if submission.student_id != student_id:
        raise BadRequestException(10007, "无权删除此提交")
    if submission.status != "draft":
        raise BadRequestException(10011, "只能删除草稿")
    _delete_attachment_files(submission.attachments)
    db.delete(submission)
    db.commit()
    return {"success": True, "message": "删除成功", "resourceId": str(submission_id)}


def teacher_delete_submission(db: Session, submission_id: int, teacher_id: int) -> dict:
    """教师删除学生提交 — 验证该提交对应的作业属于该教师，让学生可重新提交"""
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise NotFoundException(10015, "提交记录不存在")
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise NotFoundException(10015, "作业不存在")
    if assignment.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权删除此提交")
    _delete_attachment_files(submission.attachments)
    db.delete(submission)
    db.commit()
    return {"success": True, "message": "已删除学生提交，学生可重新提交", "resourceId": str(submission_id)}


# ===== AI 批改后台任务 =====

def _encode_image_to_data_uri(image_bytes: bytes) -> str | None:
    """将图片二进制编码为 data URI（用于多模态 AI 调用）"""
    try:
        from PIL import Image
        import io as _io
        im = Image.open(_io.BytesIO(image_bytes))
        fmt = (im.format or "PNG").lower()
        mime = "image/jpeg" if fmt in ("jpg", "jpeg") else f"image/{fmt}"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning("图片编码失败: %s", e)
        return None


def trigger_ai_review(submission_id: int):
    """后台任务: 提取作业文字+图片(多模态)，调用 AI 模型进行自动批改"""
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            return
        assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
        if not assignment or not assignment.ai_rule:
            return
        ai_rule = assignment.ai_rule
        prompt = ai_rule.get("prompt", "")
        model_type = ai_rule.get("modelType", "deepseek")

        # 构建多模态内容列表 [{"type":"text","text":"..."}, {"type":"image_url","image_url":{"url":"data:..."}}]
        media_items = []
        upload_dir = str(settings.upload_path)

        # ---- 0. 老师的作业要求 + 参考附件 ----
        if assignment.description:
            desc = re.sub(r"<[^>]*>", "", assignment.description or "").strip()
            if desc:
                media_items.append({
                    "type": "text",
                    "text": "【老师布置的作业要求】\n" + desc,
                })
        teacher_attachments = assignment.attachments or []
        if teacher_attachments:
            media_items.append({"type": "text", "text": "\n\n【老师提供的参考附件】"})
            for t_att in teacher_attachments:
                t_file_url = t_att.get("fileUrl", "")
                t_filename = t_file_url.replace("/uploads/", "")
                t_file_name = t_att.get("fileName", "unknown")
                t_file_type = str(t_att.get("fileType", ""))
                t_ext = os.path.splitext(t_file_name)[1].lower()

                if not t_filename:
                    continue

                t_file_path = os.path.join(upload_dir, t_filename)
                if not os.path.exists(t_file_path):
                    continue

                # 老师参考图片
                if t_file_type.startswith("image/"):
                    with open(t_file_path, "rb") as f:
                        img_bytes = f.read()
                    data_uri = _encode_image_to_data_uri(img_bytes)
                    if data_uri:
                        media_items.append({"type": "text", "text": f"\n[参考附件：{t_file_name}]"})
                        media_items.append({
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        })
                    continue

                # 老师参考 docx（含图片）
                if t_ext == ".docx":
                    try:
                        ref_text, ref_images = extract_all_from_docx(t_file_path)
                        if ref_text and ref_text.strip():
                            media_items.append({
                                "type": "text",
                                "text": f"\n--- 参考「{t_file_name}」文本内容 ---\n{ref_text}",
                            })
                        for r_i, r_bytes in enumerate(ref_images):
                            data_uri = _encode_image_to_data_uri(r_bytes)
                            if data_uri:
                                media_items.append({
                                    "type": "text",
                                    "text": f"\n[参考「{t_file_name}」内嵌图片 {r_i+1}]",
                                })
                                media_items.append({
                                    "type": "image_url",
                                    "image_url": {"url": data_uri},
                                })
                        if ref_text and ref_text.strip():
                            continue
                    except Exception as e:
                        logger.warning("[AI] 参考docx解析失败: %s: %s", t_file_path, e)

                # 其他参考文件
                ref_text = extract_file_text(t_file_path, t_ext)
                if ref_text and ref_text.strip():
                    media_items.append({
                        "type": "text",
                        "text": f"\n--- 参考「{t_file_name}」文本内容 ---\n{ref_text}",
                    })

        # ---- 1. 学生富文本编辑器内容 ----
        editor_text = re.sub(r"<[^>]*>", "", submission.content or "").strip()
        if editor_text:
            media_items.append({"type": "text", "text": "【学生作业正文】\n" + editor_text})

        # 2. 附件（docx/pdf/txt/图片）
        attachments = submission.attachments or []
        if attachments:
            media_items.append({"type": "text", "text": "\n\n【附件内容】"})
            for att in attachments:
                file_url = att.get("fileUrl", "")
                filename = file_url.replace("/uploads/", "")
                file_type = str(att.get("fileType", ""))
                file_name = att.get("fileName", "unknown")
                ext = os.path.splitext(file_name)[1].lower()

                if not filename:
                    continue

                file_path = os.path.join(upload_dir, filename)
                file_exists = os.path.exists(file_path)

                # --- 图片附件：直接编码为 base64 送给 AI ---
                if file_type.startswith("image/"):
                    if file_exists:
                        with open(file_path, "rb") as f:
                            img_bytes = f.read()
                        data_uri = _encode_image_to_data_uri(img_bytes)
                        if data_uri:
                            media_items.append({"type": "text", "text": f"\n[图片附件：{file_name}]"})
                            media_items.append({
                                "type": "image_url",
                                "image_url": {"url": data_uri},
                            })
                            continue
                    media_items.append({"type": "text", "text": f"\n[已上传图片：{file_name}]"})
                    continue

                # --- docx：同时提取文字和图片 ---
                if ext == ".docx" and file_exists:
                    try:
                        doc_text, doc_images = extract_all_from_docx(file_path)
                        if doc_text and doc_text.strip():
                            media_items.append({
                                "type": "text",
                                "text": f"\n--- 附件「{file_name}」文本内容 ---\n{doc_text}",
                            })
                        for i, img_bytes in enumerate(doc_images):
                            data_uri = _encode_image_to_data_uri(img_bytes)
                            if data_uri:
                                media_items.append({
                                    "type": "text",
                                    "text": f"\n[文档「{file_name}」内嵌图片 {i+1}]",
                                })
                                media_items.append({
                                    "type": "image_url",
                                    "image_url": {"url": data_uri},
                                })
                        if doc_text and doc_text.strip():
                            continue  # 已处理完文字+图片，跳过下面的纯文本提取
                    except Exception as e:
                        logger.warning("[AI] docx多模态提取失败: %s: %s", file_path, e)

                # --- 其他文件：仅提取文字 ---
                text = ""
                if file_exists:
                    text = extract_file_text(file_path, ext)
                if not text or not text.strip():
                    text = att.get("textContent", "")
                if text and text.strip():
                    media_items.append({
                        "type": "text",
                        "text": f"\n--- 附件「{file_name}」文本内容 ---\n{text}",
                    })
                else:
                    media_items.append({
                        "type": "text",
                        "text": f"\n[已上传文件：{file_name}]",
                    })

        model_config = db.query(AiModel).filter(AiModel.code == model_type).first()
        if not model_config or not (model_config.api_key or "").strip():
            logger.warning("[AI] 批改跳过: %s API Key未配置", model_type)
            return

        try:
            score, content, tokens = _call_ai_api(model_config, prompt, media_items)
            if score is None:
                submission.ai_review_content = content
                submission.ai_score = None
                logger.warning("[AI] 分数解析失败: 作业%s, 提交%s", assignment.id, submission.id)
            else:
                submission.ai_score = score
                submission.ai_review_content = content
                submission.status = "ai_reviewed"
            db.commit()
            if score is not None:
                model_config.total_usage = (model_config.total_usage or 0) + 1
                model_config.total_tokens = (model_config.total_tokens or 0) + (tokens or 100)
                model_config.last_used_at = now()
                db.commit()
            logger.info("[AI] 批改完成: 作业%s, 得分%s, 图片数%s", assignment.id, score,
                        sum(1 for m in media_items if m.get("type") == "image_url"))
        except Exception as e:
            logger.error("[AI] 批改失败: %s", e, exc_info=True)
            try:
                submission.ai_review_content = f"⚠️ AI批改失败，请教师人工批改。\n\n错误信息：{e}"
                submission.ai_score = None
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()


def _call_ai_api(model_config: AiModel, system_prompt: str, media_items: list[dict]):
    """调用多模态 AI 接口(OpenAI 兼容 vision format) — 支持文字+图片混合输入"""
    format_instructions = (
        "\n【输出格式要求】\n1. 请使用中文进行批改回答\n"
        "2. 在开头用 **【总分：XX分】** 标明总分\n"
        "3. 每个评分维度用 **1. 维度名：XX分** 格式加粗标注\n"
        "4. 优点用 ✅ 开头，改进建议用 📝 开头\n5. 关键分数和评语用 **粗体** 突出显示\n"
        "6. 整体评价用简短总结，不要过长\n"
        "7. 请结合学生上传的图片内容进行评判（图表、截图、手写内容等）\n"
        "8. 请对照上方「老师布置的作业要求」和「老师提供的参考附件」，判断学生是否达到要求"
    )

    # 构建多模态消息内容
    message_content = [
        {"type": "text", "text": f"{system_prompt}\n\n{format_instructions}\n\n【学生作业内容】"}
    ]
    message_content.extend(media_items)

    api_url = f"{model_config.base_url}/chat/completions"
    with httpx.Client(timeout=120) as client:  # 多模态可能较慢，放宽超时
        resp = client.post(api_url, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config.api_key}",
        }, json={
            "model": model_config.model_name,
            "messages": [{"role": "user", "content": message_content}],
            "temperature": 0.7, "max_tokens": 2000,
        })
        resp.raise_for_status()
        result = resp.json()
    ai_text = (result.get("choices") or [{}])[0].get("message", {}).get("content", "")
    tokens = result.get("usage", {}).get("total_tokens", 0)
    m = re.search(r"总分[：:]\s*(\d+)\s*分", ai_text)
    if m:
        score = int(m.group(1))
    else:
        score = None
        ai_text = (
            "⚠️ AI 评分解析失败，请教师人工复核。\n\n"
            "（AI 回复中未找到「总分：XX分」格式的分数）\n\n---\n\n"
            + ai_text
        )
    return score, ai_text, tokens
