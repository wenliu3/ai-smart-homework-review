"""提交 CRUD。

AI 批改经 tasks/grading.py 的 Celery 双 Agent 工作流触发；
旧直连批改链路已删除（规划 4.6 / 决策 D4），用量统计在网关层。
"""
import os
import re
import logging
from sqlalchemy import case, update
from sqlalchemy.orm import Session
from ..models import Assignment, Submission, ClassStudent
from ..core.exceptions import BadRequestException, NotFoundException
from ..core.utils import now
from ..plagiarism.extractors import extract_file_text
from ..plagiarism import get_word_tokens
from ..config import settings
from .assignment import get_student_visible_assignment

logger = logging.getLogger(__name__)


def apply_ai_grading_result(
    db: Session,
    submission_id: int,
    expected_submission_count: int,
    outcome,
) -> bool:
    """按提交版本原子写回 AI 批改结果。

    条件 UPDATE 保证旧 Worker 不能覆盖学生重新提交后的新版本。这里只更新
    AI 字段；教师评分和教师评语从不出现在 values 中。教师已经完成批改时，
    状态保持 ``teacher_reviewed``。
    """

    primary = outcome.primary
    review_note = ""
    if outcome.needs_human_review:
        reasons = list(getattr(outcome, "review_reasons", []) or [])
        reason_text = (
            "；".join(reasons)
            if reasons
            else "两次独立评分差异超过满分 10%"
        )
        review_note = f"\n\n⚠️ 需要教师人工复核：{reason_text}。"
    content = primary.summary + review_note
    statement = (
        update(Submission)
        .where(
            Submission.id == submission_id,
            Submission.submission_count == expected_submission_count,
        )
        .values(
            ai_score=primary.total_score,
            ai_review_content=content,
            ai_review_items=[
                item.model_dump(mode="json") for item in primary.items
            ],
            status=case(
                (
                    Submission.status == "teacher_reviewed",
                    Submission.status,
                ),
                else_=(
                    "submitted"
                    if outcome.needs_human_review
                    else "ai_reviewed"
                ),
            ),
        )
    )
    result = db.execute(statement)
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def mark_submission_needs_manual_grading(
    db: Session,
    submission_id: int,
    expected_submission_count: int,
    note: str,
) -> bool:
    """AI 批改降级转人工：只写提示文案，不写任何分数（规划 3B.2）。

    与 apply_ai_grading_result 同样按提交版本条件更新；
    教师已人工批改的提交保持 teacher_reviewed 状态不动。
    """
    statement = (
        update(Submission)
        .where(
            Submission.id == submission_id,
            Submission.submission_count == expected_submission_count,
        )
        .values(
            ai_review_content=note,
            status=case(
                (
                    Submission.status == "teacher_reviewed",
                    Submission.status,
                ),
                else_="submitted",
            ),
        )
    )
    result = db.execute(statement)
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


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


def _ai_review_items_to_api(items) -> list | None:
    """把落库的 snake_case 分项数组转成前端 camelCase 结构。

    每一项固定输出六键（缺失置默认），保证学生端分项卡渲染稳定；
    无分项（旧数据 / 单维度规则）时返回 None，前端保持纯文本展示。
    """
    if not items:
        return None
    result = []
    for item in items:
        result.append({
            "criterionId": item.get("criterion_id"),
            "title": item.get("title"),
            "score": item.get("score"),
            "maxScore": item.get("max_score"),
            "feedback": item.get("feedback") or "",
            "evidenceRefs": item.get("evidence_refs") or [],
        })
    return result


def submit(db: Session, student_id: int, data: dict) -> dict:
    """学生提交作业 — 若已有提交则更新(允许重复提交)，草稿不触发 AI 批改"""
    assignment_id = data.get("assignmentId")
    assignment = db.query(Assignment).filter(Assignment.alive(), Assignment.id == int(assignment_id)).first()
    if not assignment:
        raise NotFoundException(10015, "作业不存在")
    if assignment.status != "published":
        raise BadRequestException(10011, "作业不可提交")
    assigned_class_ids = {
        int(item["id"])
        for item in (assignment.classes or [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    requested_class_id = int(data.get("classId") or 0)
    if requested_class_id not in assigned_class_ids:
        raise BadRequestException(10007, "该作业未布置给指定班级")
    membership = db.query(ClassStudent).filter(
        ClassStudent.class_id == requested_class_id,
        ClassStudent.student_id == student_id,
        ClassStudent.status == "active",
    ).first()
    if membership is None:
        raise BadRequestException(10007, "当前学生不属于该作业班级")
    is_draft = data.get("isDraft", False)
    if not is_draft and assignment.end_date and now() > assignment.end_date:
        raise BadRequestException(10011, "作业已截止，无法提交")

    attachments = data.get("attachments", []) or []
    if attachments and not bool(assignment.allow_attachments):
        raise BadRequestException(10011, "该作业不允许上传附件")
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
            submission.ai_review_items = None
    else:
        submission = Submission(
            assignment_id=assignment.id, student_id=student_id,
            class_id=requested_class_id, content=content, attachments=attachments, word_count=word_count,
            is_draft=is_draft, status="draft" if is_draft else "submitted",
            submitted_at=None if is_draft else now(), submission_count=1,
        )
        db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def get_my_submission(db: Session, assignment_id: int, student_id: int) -> dict:
    """学生查看自己的提交详情 — 含作业信息、提交内容、AI批改结果、教师批改结果"""
    assignment = get_student_visible_assignment(db, assignment_id, student_id)
    submission = db.query(Submission).filter(
        Submission.assignment_id == assignment_id, Submission.student_id == student_id
    ).first()
    max_score = _max_score(assignment)

    result = {
        "assignment": {
            "id": str(assignment.id), "title": assignment.title, "description": assignment.description,
            "attachments": assignment.attachments or [],
            "allowAttachments": bool(assignment.allow_attachments),
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
            "gradingRunId": submission.grading_run_id,  # 批改进度轮询入口（规划 3B.3）
        }
        if submission.ai_score is not None:
            result["aiReview"] = {
                "content": submission.ai_review_content or "",
                "score": _to100(submission.ai_score, max_score),
                "rawScore": submission.ai_score, "rawMaxScore": max_score,
                "items": _ai_review_items_to_api(submission.ai_review_items),
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
    assignment = db.query(Assignment).filter(Assignment.alive(), Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise NotFoundException(10015, "作业不存在")
    if assignment.teacher_id != teacher_id:
        raise BadRequestException(10007, "无权删除此提交")
    _delete_attachment_files(submission.attachments)
    db.delete(submission)
    db.commit()
    return {"success": True, "message": "已删除学生提交，学生可重新提交", "resourceId": str(submission_id)}


