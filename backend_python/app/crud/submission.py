"""提交 CRUD + AI 批改触发"""
import os
import re
import logging
import httpx
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import User, Assignment, Submission, AiModel
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.utils import now
from ..plagiarism.extractors import extract_file_text
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

def trigger_ai_review(submission_id: int):
    """后台任务: 提取作业文本(含附件)，调用 AI 模型接口进行自动批改，写入得分和评语"""
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

        attachments = submission.attachments or []
        content_text = re.sub(r"<[^>]*>", "", submission.content or "").strip()
        if attachments:
            content_text += "\n\n【附件内容】"
            upload_dir = str(settings.upload_path)
            for att in attachments:
                text = ""
                file_url = att.get("fileUrl", "")
                filename = file_url.replace("/uploads/", "")
                if filename:
                    file_path = os.path.join(upload_dir, filename)
                    if not os.path.exists(file_path):
                        logger.warning("[AI] 附件文件不存在: %s, 回退到 textContent", file_path)
                    ext = os.path.splitext(att.get("fileName", ""))[1].lower()
                    text = extract_file_text(file_path, ext)
                # 文件不存在或提取失败时，回退到上传时已存储的 textContent
                if not text or not text.strip():
                    text = att.get("textContent", "")
                if text and text.strip():
                    content_text += f"\n--- 附件「{att.get('fileName')}」文本内容 ---\n{text}"
                else:
                    label = "图片" if str(att.get("fileType", "")).startswith("image/") else "文档"
                    size_kb = (att.get("fileSize") or 0) / 1024
                    content_text += f"\n[已上传{label}：{att.get('fileName')}，{size_kb:.1f}KB]"

        model_config = db.query(AiModel).filter(AiModel.code == model_type).first()
        if not model_config or not (model_config.api_key or "").strip():
            logger.warning("[AI] 批改跳过: %s API Key未配置", model_type)
            return

        try:
            score, content, tokens = _call_ai_api(model_config, prompt, content_text)
            # 分数为 None 表示 AI 回复格式不规范，无法提取总分
            if score is None:
                submission.ai_review_content = content
                submission.ai_score = None
                # 保持 submitted 状态，等待教师人工批改
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
            logger.info("[AI] 批改完成: 作业%s, 得分%s", assignment.id, score)
        except Exception as e:
            logger.error("[AI] 批改失败: %s", e, exc_info=True)
            # 标记 AI 批改异常，保留 submitted 状态等待教师人工批改
            try:
                submission.ai_review_content = f"⚠️ AI批改失败，请教师人工批改。\n\n错误信息：{e}"
                submission.ai_score = None
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()


def _call_ai_api(model_config: AiModel, system_prompt: str, user_content: str):
    """调用 OpenAI 兼容格式的 AI 接口(chat/completions) — 从回复中正则提取总分"""
    format_instructions = (
        "\n【输出格式要求】\n1. 请使用中文进行批改回答\n"
        "2. 在开头用 **【总分：XX分】** 标明总分\n"
        "3. 每个评分维度用 **1. 维度名：XX分** 格式加粗标注\n"
        "4. 优点用 ✅ 开头，改进建议用 📝 开头\n5. 关键分数和评语用 **粗体** 突出显示\n"
        "6. 整体评价用简短总结，不要过长"
    )
    full_prompt = f"{system_prompt}\n\n{format_instructions}\n\n【学生作业内容】\n{user_content}"
    api_url = f"{model_config.base_url}/chat/completions"
    with httpx.Client(timeout=60) as client:
        resp = client.post(api_url, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config.api_key}",
        }, json={
            "model": model_config.model_name,
            "messages": [{"role": "user", "content": full_prompt}],
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
        # 分数解析失败：不随机给分，返回 None 让调用方决定处理方式
        score = None
        ai_text = (
            "⚠️ AI 评分解析失败，请教师人工复核。\n\n"
            "（AI 回复中未找到「总分：XX分」格式的分数）\n\n---\n\n"
            + ai_text
        )
    return score, ai_text, tokens
