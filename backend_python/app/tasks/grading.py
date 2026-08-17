"""批改任务的版本幂等边界。

批改核心采用 7 月 15 版直接调用方法：构建多模态媒体消息 → 直接调 AI →
正则提取「总分：XX分」→ 写回 submission。不再使用 LangGraph 图、
JSON 结构化校验或 tool_choice（对部分模型不稳定）。

保留的既有基础设施：
- Celery 异步任务（run_grading_task / GradingTask 硬超时收口）；
- 提交版本幂等（enqueue_grading_job / build_grading_idempotency_key）；
- 受控失败 GradingRoutingError / AGENT_RULE_MODEL_NOT_CONFIGURED
  （作业未配置规则模型 modelType 时在模型调用前受控失败）；
- finalize_run 写 run 终态与 Artifact（grading_outcome / grading_raw_draft）。
"""
from __future__ import annotations

import base64
import hashlib
import html
import httpx
import logging
import os
import re

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..agent.contracts import (
    AGENT_GRADING_TIMEOUT,
    AGENT_RULE_MODEL_NOT_CONFIGURED,
    GradingRubric,
    RubricCriterion,
)
from ..agent.runtime import BudgetExceeded
from ..assistant_database import AssistantSessionLocal
from ..config import settings
from ..crud import agent_run, agent_session
from ..crud.submission import mark_submission_needs_manual_grading
from ..database import SessionLocal
from ..models import (
    AgentRun,
    AgentSession,
    AiModel,
    Assignment,
    Submission,
)
from ..plagiarism.extractors import extract_all_from_docx, extract_file_text
from .celery_app import celery_app
from .grading_request import GradingTask

logger = logging.getLogger(__name__)

# 降级转人工时写给教师端的提示（服务端文案，不经模型）
MANUAL_GRADING_NOTE = (
    "⚠️ AI 批改未能生成有效的结构化评分，本次提交需要教师人工批改。"
)

# 单个文本块进入模型消息的字符上限：长文档/大附件会撑爆模型上下文
_TEXT_CHAR_LIMIT = 8000
# 单份 docx 最多提取的内嵌图片数：防止图片密集文档撑爆多模态输入
_DOCX_EMBED_IMAGE_LIMIT = 6
# 批改强调同一量表下的评分一致性，使用低温度减少随机波动
_GRADING_TEMPERATURE = 0.2
# 总分提取正则：兼容「总分：85分」「总分:90分」
_SCORE_RE = re.compile(r"总分[：:]\s*(\d+)\s*分")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


def _strip_html(text: str) -> str:
    """去掉 HTML 标签并归一化空白，保留纯文本内容。"""
    text = html.unescape(_TAG_RE.sub("", text or ""))
    text = _WS_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _truncate_block(text: str) -> str:
    """单个文本块截断到 _TEXT_CHAR_LIMIT，防止超大输入。"""
    text = text or ""
    if len(text) <= _TEXT_CHAR_LIMIT:
        return text
    return text[:_TEXT_CHAR_LIMIT]


def _encode_image_to_data_uri(image_bytes: bytes) -> str | None:
    """将图片二进制编码为 data URI（用于多模态 AI 调用）。"""
    try:
        from PIL import Image
        import io as _io

        im = Image.open(_io.BytesIO(image_bytes))
        fmt = (im.format or "PNG").lower()
        mime = "image/jpeg" if fmt in ("jpg", "jpeg") else f"image/{fmt}"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        logger.warning("图片编码失败", exc_info=True)
        return None


def _coerce_text_content(content) -> str:
    """把模型响应的 content 归一化为纯文本。

    langchain 多模态模型的 content 可能是字符串，也可能是分块列表
    （[{type: text, text: ...}, ...]）；这里统一取文本块拼接。
    """
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def build_grading_idempotency_key(
    submission_id: int,
    submission_count: int,
    rubric_version: str,
) -> str:
    """生成可读且稳定的业务幂等键。"""

    if submission_id <= 0 or submission_count <= 0:
        raise ValueError("submission_id 和 submission_count 必须为正整数")
    version = rubric_version.strip()
    if not version:
        raise ValueError("rubric_version 不能为空")
    return (
        f"grading:submission:{submission_id}:version:{submission_count}:"
        f"rubric:{version}"
    )


def rubric_from_ai_rule(ai_rule: dict) -> GradingRubric:
    """把新旧 AI 规则统一为版本化评分量表。"""

    criteria_data = ai_rule.get("criteria") or []
    if criteria_data:
        criteria = [
            RubricCriterion(
                criterion_id=str(item.get("id") or item.get("criterionId")),
                title=str(item.get("title") or item.get("name")),
                max_score=float(item.get("maxScore", item.get("max_score"))),
                instructions=str(item.get("instructions") or ""),
            )
            for item in criteria_data
        ]
        version = str(
            ai_rule.get("version")
            or ai_rule.get("rubricVersion")
            or "rubric-v1"
        )
        return GradingRubric(version=version, criteria=criteria)

    max_score = float(ai_rule.get("maxScore") or 100)
    fingerprint = hashlib.sha256(
        repr(sorted(ai_rule.items())).encode("utf-8"),
    ).hexdigest()[:12]
    version = str(
        ai_rule.get("version")
        or ai_rule.get("rubricVersion")
        or f"legacy-{fingerprint}"
    )
    return GradingRubric(
        version=version,
        criteria=[RubricCriterion(
            criterion_id="overall",
            title="综合质量",
            max_score=max_score,
            instructions=str(ai_rule.get("prompt") or ""),
        )],
    )


def _session_id_for_key(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:40]
    return f"grading-{digest}"


def enqueue_grading_job(
    business_db: Session,
    run_db: Session,
    *,
    submission: Submission,
    user_id: int,
    actor_role: str,
) -> str | None:
    """创建持久化 Run，并且每个提交版本只投递一次。"""

    assignment = business_db.query(Assignment).filter(
        Assignment.alive(),
        Assignment.id == submission.assignment_id,
    ).first()
    if not assignment or not assignment.ai_rule:
        return None
    rubric = rubric_from_ai_rule(assignment.ai_rule)
    key = build_grading_idempotency_key(
        submission.id,
        submission.submission_count,
        rubric.version,
    )
    session_id = _session_id_for_key(key)
    session = run_db.query(AgentSession).filter(
        AgentSession.id == session_id,
    ).first()
    if session is None:
        try:
            agent_session.create_session(
                run_db,
                user_id=user_id,
                actor_role=actor_role,
                session_id=session_id,
                title=f"批改任务：{assignment.title}",
            )
        except IntegrityError:
            run_db.rollback()
            session = run_db.query(AgentSession).filter(
                AgentSession.id == session_id,
            ).first()
            if (
                session is None
                or session.user_id != user_id
                or session.actor_role != actor_role
            ):
                raise
    elif session.user_id != user_id or session.actor_role != actor_role:
        raise ValueError("批改任务会话归属冲突")

    existing = (
        run_db.query(AgentRun)
        .filter(
            AgentRun.session_id == session_id,
            AgentRun.user_id == user_id,
            AgentRun.intent == "grading",
            AgentRun.status.in_(["running", "completed"]),
        )
        .order_by(AgentRun.created_at.desc())
        .first()
    )
    if existing is not None:
        _record_grading_run_id(business_db, submission, existing.id)
        return existing.id

    deterministic_run_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
    try:
        run = agent_run.create_run(
            run_db,
            session_id=session_id,
            user_id=user_id,
            intent="grading",
            risk_level="medium",
            graph_version="grading-v1",
            run_id=deterministic_run_id,
        )
    except IntegrityError:
        run_db.rollback()
        run = agent_run.get_run(run_db, deterministic_run_id, user_id)
        if run is None:
            raise
        _record_grading_run_id(business_db, submission, run.id)
        return run.id
    try:
        run_grading_task.delay(
            submission_id=submission.id,
            submission_count=submission.submission_count,
            rubric_version=rubric.version,
            run_id=run.id,
            user_id=user_id,
        )
    except Exception:
        agent_run.fail_run(
            run_db,
            run.id,
            user_id,
            "AGENT_QUEUE_UNAVAILABLE",
        )
        raise
    _record_grading_run_id(business_db, submission, run.id)
    return run.id


def _record_grading_run_id(
    business_db: Session,
    submission: Submission,
    run_id: str,
) -> None:
    """把批改 run 记到提交行：学生轮询进度、教师查产物都由此定位。"""
    if submission.grading_run_id == run_id:
        return
    submission.grading_run_id = run_id
    business_db.commit()


class GradingRoutingError(Exception):
    """任务层受控失败：批改运行配置无效，需以稳定错误码标记 run。

    覆盖「作业未配置规则模型」配置错误；
    code 为 contracts 里的稳定错误码（如 AGENT_RULE_MODEL_NOT_CONFIGURED），
    由 execute_grading_job 的 except 分支写到 run.error_code。
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _grading_routing_config(business_db: Session, assignment: Assignment) -> dict:
    """构造批改链路的显式运行配置：规则模型 code。

    规则模型 code 只来自作业快照 ai_rule.modelType，**绝不回退默认模型**；
    缺少时抛 GradingRoutingError（稳定错误码 AGENT_RULE_MODEL_NOT_CONFIGURED）。
    """
    ai_rule = assignment.ai_rule or {}
    rule_model_code = str(ai_rule.get("modelType") or "").strip()
    if not rule_model_code:
        raise GradingRoutingError(
            AGENT_RULE_MODEL_NOT_CONFIGURED,
            "作业 AI 规则未配置规则模型（modelType），无法发起批改",
        )
    return {
        "rule_model_code": rule_model_code,
        "rule_prompt": str(ai_rule.get("prompt") or "").strip(),
    }


def _grading_prompt_text(assignment) -> str:
    """拼装 AI 评分规则 + 可选多维度提示 + 输出格式要求。"""
    ai_rule = assignment.ai_rule or {}
    parts: list[str] = []

    prompt = str(ai_rule.get("prompt") or "").strip()
    if prompt:
        parts.append(prompt)

    criteria = ai_rule.get("criteria")
    if criteria:
        lines = []
        for index, item in enumerate(criteria, 1):
            title = str(item.get("title") or item.get("name") or f"维度{index}")
            max_score = item.get("maxScore", item.get("max_score", ""))
            instructions = str(item.get("instructions") or "").strip()
            line = f"{index}. {title}（满分{max_score}）"
            if instructions:
                line += f"：{instructions}"
            lines.append(line)
        parts.append(
            "评分维度（请严格按以下维度逐项评分，不得自创、拆分或合并维度）：\n"
            + "\n".join(lines)
        )

    parts.append(
        "【输出格式要求】\n"
        "1. 请使用中文进行批改回答\n"
        "2. 在开头用 **【总分：XX分】** 标明总分\n"
        "3. 每个评分维度用 **1. 维度名：XX分** 格式加粗标注\n"
        "4. 优点用 ✅ 开头，改进建议用 📝 开头\n"
        "5. 关键分数和评语用 **粗体** 突出显示\n"
        "6. 整体评价用简短总结，不要过长\n"
        "7. 请结合学生上传的图片内容进行评判（图表、截图、手写内容等）\n"
        "8. 请对照上方「老师布置的作业要求」和「老师提供的参考附件」，判断学生是否达到要求"
    )
    return "\n\n".join(parts)


def _build_media_items(
    submission: Submission,
    assignment: Assignment,
    upload_dir,
) -> list[dict]:
    """构建多模态媒体消息列表。

    顺序：老师作业要求（去 HTML）→ 老师参考附件（docx 文本+内嵌图片、
    图片 data URI、其他文本）→ 学生富文本正文（去 HTML）→ 学生附件。
    文本块统一截断到 _TEXT_CHAR_LIMIT，docx 内嵌图片上限
    _DOCX_EMBED_IMAGE_LIMIT 张，防止超大输入撑爆模型上下文。
    """
    media_items: list[dict] = []

    # ---- 0. 老师的作业要求 + 参考附件 ----
    desc = _strip_html(assignment.description or "")
    if desc:
        media_items.append({
            "type": "text",
            "text": "【老师布置的作业要求】\n" + _truncate_block(desc),
        })
    teacher_attachments = assignment.attachments or []
    if teacher_attachments:
        media_items.append({"type": "text", "text": "\n\n【老师提供的参考附件】"})
        for t_att in teacher_attachments:
            t_file_url = str(t_att.get("fileUrl", ""))
            t_filename = t_file_url.replace("/uploads/", "")
            t_file_name = str(t_att.get("fileName", "unknown"))
            t_file_type = str(t_att.get("fileType", ""))
            t_ext = os.path.splitext(t_file_name)[1].lower()
            if not t_filename:
                continue
            t_file_path = os.path.join(upload_dir, t_filename)
            if not os.path.exists(t_file_path):
                continue
            # 参考图片 → data URI
            if t_file_type.startswith("image/"):
                with open(t_file_path, "rb") as f:
                    img_bytes = f.read()
                data_uri = _encode_image_to_data_uri(img_bytes)
                if data_uri:
                    media_items.append({
                        "type": "text",
                        "text": f"\n[参考附件：{t_file_name}]",
                    })
                    media_items.append({
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    })
                continue
            # 参考 docx（文本 + 内嵌图片）
            if t_ext == ".docx":
                try:
                    ref_text, ref_images = extract_all_from_docx(t_file_path)
                except Exception as e:
                    logger.warning(
                        "[AI] 参考docx解析失败: %s: %s", t_file_path, e,
                    )
                    ref_text, ref_images = "", []
                if ref_text and ref_text.strip():
                    media_items.append({
                        "type": "text",
                        "text": (
                            f"\n--- 参考「{t_file_name}」文本内容 ---\n"
                            f"{_truncate_block(ref_text)}"
                        ),
                    })
                for r_i, r_bytes in enumerate(
                    ref_images[:_DOCX_EMBED_IMAGE_LIMIT],
                ):
                    data_uri = _encode_image_to_data_uri(bytes(r_bytes))
                    if data_uri:
                        media_items.append({
                            "type": "text",
                            "text": f"\n[参考「{t_file_name}」内嵌图片 {r_i + 1}]",
                        })
                        media_items.append({
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        })
                if ref_text and ref_text.strip():
                    continue
            # 其他参考文件：仅提取文本
            ref_text = extract_file_text(t_file_path, t_ext)
            if ref_text and ref_text.strip():
                media_items.append({
                    "type": "text",
                    "text": (
                        f"\n--- 参考「{t_file_name}」文本内容 ---\n"
                        f"{_truncate_block(ref_text)}"
                    ),
                })

    # ---- 1. 学生富文本编辑器内容 ----
    editor_text = _strip_html(submission.content or "")
    if editor_text:
        media_items.append({
            "type": "text",
            "text": "【学生作业正文】\n" + _truncate_block(editor_text),
        })

    # ---- 2. 学生附件（docx/pdf/txt/图片） ----
    attachments = submission.attachments or []
    if attachments:
        media_items.append({"type": "text", "text": "\n\n【附件内容】"})
        for att in attachments:
            file_url = str(att.get("fileUrl", ""))
            filename = file_url.replace("/uploads/", "")
            file_type = str(att.get("fileType", ""))
            file_name = str(att.get("fileName", "unknown"))
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
                        media_items.append({
                            "type": "text",
                            "text": f"\n[图片附件：{file_name}]",
                        })
                        media_items.append({
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        })
                        continue
                media_items.append({
                    "type": "text",
                    "text": f"\n[已上传图片：{file_name}]",
                })
                continue

            # --- docx：同时提取文字和图片 ---
            if ext == ".docx" and file_exists:
                try:
                    doc_text, doc_images = extract_all_from_docx(file_path)
                except Exception as e:
                    logger.warning(
                        "[AI] docx多模态提取失败: %s: %s", file_path, e,
                    )
                    doc_text, doc_images = "", []
                if doc_text and doc_text.strip():
                    media_items.append({
                        "type": "text",
                        "text": (
                            f"\n--- 附件「{file_name}」文本内容 ---\n"
                            f"{_truncate_block(doc_text)}"
                        ),
                    })
                for i, img_bytes in enumerate(doc_images[:_DOCX_EMBED_IMAGE_LIMIT]):
                    data_uri = _encode_image_to_data_uri(bytes(img_bytes))
                    if data_uri:
                        media_items.append({
                            "type": "text",
                            "text": f"\n[文档「{file_name}」内嵌图片 {i + 1}]",
                        })
                        media_items.append({
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        })
                if doc_text and doc_text.strip():
                    continue  # 已处理完文字+图片，跳过下面的纯文本提取

            # --- 其他文件：仅提取文字 ---
            text = ""
            if file_exists:
                text = extract_file_text(file_path, ext)
            if not text or not text.strip():
                text = str(att.get("textContent", ""))
            if text and text.strip():
                media_items.append({
                    "type": "text",
                    "text": (
                        f"\n--- 附件「{file_name}」文本内容 ---\n"
                        f"{_truncate_block(text)}"
                    ),
                })
            else:
                media_items.append({
                    "type": "text",
                    "text": f"\n[已上传文件：{file_name}]",
                })
    return media_items


def _run_ai_grading(
    business_db: Session,
    submission: Submission,
    assignment: Assignment,
    rubric=None,  # 兼容旧 runner 签名；直接调 AI 方法不再做量表校验
) -> dict:
    """直接调 AI 批改（7 月 15 版方法）：多模态消息 → 正则提取总分。

    沿用 7/15 版 OpenAI 兼容 chat/completions 多模态格式、max_tokens=2000
    与 120s 超时；temperature 降为 0.2，减少同一量表重复批改时的随机波动。
    DeepSeek V4 默认 thinking 不支持 tool_choice，沿用 gateway 约定经请求体
    thinking.disabled 关闭。

    返回 {"score": int|None, "content": ai_text, "model_code": ...}。
    score 为 None（未找到「总分：XX分」）时 content 前缀加人工复核提示。
    """
    model_code = _grading_routing_config(business_db, assignment)["rule_model_code"]
    model = (
        business_db.query(AiModel)
        .filter(AiModel.code == model_code, AiModel.status == "active")
        .first()
    )
    if model is None:
        raise GradingRoutingError(
            AGENT_RULE_MODEL_NOT_CONFIGURED,
            f"未找到启用状态下的 AI 规则模型「{model_code}」",
        )
    if not (model.api_key or "").strip():
        raise GradingRoutingError(
            AGENT_RULE_MODEL_NOT_CONFIGURED,
            f"AI 规则模型「{model.name}」未配置 API Key",
        )

    prompt = _grading_prompt_text(assignment)
    media_items = _build_media_items(
        submission,
        assignment,
        settings.upload_path,
    )
    message_content = [
        {"type": "text", "text": f"{prompt}\n\n【学生作业内容】"},
        *media_items,
    ]
    payload: dict = {
        "model": model.model_name,
        "messages": [{"role": "user", "content": message_content}],
        "temperature": _GRADING_TEMPERATURE,
        "max_tokens": 2000,
    }
    provider = (model.provider or "").lower()
    if "deepseek" in provider and "v4" in (model.model_name or "").lower():
        payload["thinking"] = {"type": "disabled"}

    api_url = f"{model.base_url}/chat/completions"
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                api_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {model.api_key}",
                },
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPError as exc:
        raise GradingRoutingError(
            AGENT_RULE_MODEL_NOT_CONFIGURED,
            f"AI 批改调用失败：{exc}",
        ) from exc

    ai_text = _coerce_text_content(
        (result.get("choices") or [{}])[0].get("message", {}).get("content", ""),
    )
    match = _SCORE_RE.search(ai_text)
    if match:
        score = int(match.group(1))
    else:
        score = None
        ai_text = "⚠️ AI 评分解析失败，请教师人工复核。\n\n" + ai_text
    return {"score": score, "content": ai_text, "model_code": model_code}


def _write_ai_grading_result(
    business_db: Session,
    submission_id: int,
    expected_submission_count: int,
    *,
    score: int,
    content: str,
) -> bool:
    """按提交版本原子写回 AI 批改结果（直接写 submission 字段）。

    条件 UPDATE 保证旧 Worker 不能覆盖学生重新提交后的新版本；
    教师已批改的提交保持 teacher_reviewed 状态。ai_review_items 列保留
    但新方法不写（置 None）。
    """
    statement = (
        update(Submission)
        .where(
            Submission.id == submission_id,
            Submission.submission_count == expected_submission_count,
        )
        .values(
            ai_score=score,
            ai_review_content=content,
            ai_review_items=None,
            status=case(
                (
                    Submission.status == "teacher_reviewed",
                    Submission.status,
                ),
                else_="ai_reviewed",
            ),
        )
    )
    result = business_db.execute(statement)
    if result.rowcount != 1:
        business_db.rollback()
        return False
    business_db.commit()
    return True


def _fail_run_with_code(
    audit: Session,
    run_id: str,
    user_id: int,
    code: str,
) -> None:
    """把仍在 running/processing 的批改 run 标记为 failed 并写入稳定错误码。

    execute_grading_job 的受控失败分支共用；仅当前状态可失败时才落库，
    终态（completed/cancelled/failed）保持不变。调用方用
    `try: _fail_run_with_code(...) finally: raise` 保证原异常继续上抛。
    """
    existing = agent_run.get_run(audit, run_id, user_id)
    if (
        existing is not None
        and existing.status in {"running", "processing"}
    ):
        agent_run.fail_run(audit, run_id, user_id, code)


def execute_grading_job(
    *,
    submission_id: int,
    submission_count: int,
    rubric_version: str,
    run_id: str,
    user_id: int,
    business_db: Session | None = None,
    run_db: Session | None = None,
    workflow_runner=None,
) -> dict:
    """执行可安全重跑的批改任务并持久化 Step/Artifact。"""

    owns_business_db = business_db is None
    owns_run_db = run_db is None
    biz = business_db or SessionLocal()
    audit = run_db or AssistantSessionLocal()
    try:
        run = agent_run.get_run(audit, run_id, user_id)
        if run is None:
            raise ValueError("批改运行不存在或不属于当前用户")
        if run.status == "cancelled":
            return {"status": "cancelled", "run_id": run_id}
        if run.status == "completed":
            return {"status": "completed", "run_id": run_id}
        if run.status not in {"running", "processing"}:
            return {"status": run.status, "run_id": run_id}
        claimed = (
            audit.query(AgentRun)
            .filter(
                AgentRun.id == run_id,
                AgentRun.user_id == user_id,
                AgentRun.status.in_(["running", "processing"]),
            )
            .update(
                {AgentRun.status: "processing"},
                synchronize_session=False,
            )
        )
        audit.commit()
        if claimed != 1:
            current = agent_run.get_run(audit, run_id, user_id)
            return {
                "status": current.status if current else "missing",
                "run_id": run_id,
            }

        submission = biz.query(Submission).filter(
            Submission.id == submission_id,
        ).first()
        if (
            submission is None
            or submission.submission_count != submission_count
        ):
            agent_run.finalize_run(
                audit,
                run_id,
                user_id,
                final_output="提交版本已变化，旧批改任务未写回。",
                artifacts=[{
                    "artifact_type": "grading_stale",
                    "schema_version": "v1",
                    "payload": {
                        "submission_id": submission_id,
                        "expected_submission_count": submission_count,
                    },
                }],
            )
            return {"status": "stale", "run_id": run_id}

        assignment = biz.query(Assignment).filter(
            Assignment.alive(),
            Assignment.id == submission.assignment_id,
        ).first()
        if not assignment or not assignment.ai_rule:
            raise ValueError("作业未配置 AI 评分规则")
        rubric = rubric_from_ai_rule(assignment.ai_rule)
        if rubric.version != rubric_version:
            raise ValueError("评分量表版本已变化")

        runner = workflow_runner or _run_ai_grading
        try:
            result = runner(biz, submission, assignment, rubric)
        except BudgetExceeded as exc:
            # 预算耗尽与结构化失败同等处理：转人工，不丢结果不炸任务
            result = {
                "score": None,
                "content": f"⚠️ AI 批改预算耗尽，请教师人工复核：{exc}",
                "model_code": None,
            }

        audit.expire_all()
        current_run = agent_run.get_run(audit, run_id, user_id)
        if current_run is None or current_run.status == "cancelled":
            return {"status": "cancelled", "run_id": run_id}

        score = result.get("score")
        content = result.get("content") or ""
        if score is None:
            # 降级转人工：原始全文留证到 Artifact，教师端拿到明确提示；
            # run 记为 completed——这是受控降级，不是任务失败
            mark_submission_needs_manual_grading(
                biz,
                submission_id=submission_id,
                expected_submission_count=submission_count,
                note=content or MANUAL_GRADING_NOTE,
            )
            agent_run.finalize_run(
                audit,
                run_id,
                user_id,
                final_output="AI 批改未生成有效评分，已转教师人工批改。",
                artifacts=[{
                    "artifact_type": "grading_raw_draft",
                    "schema_version": "v1",
                    "payload": {"content": content},
                }],
                usage=None,
            )
            return {"status": "completed", "run_id": run_id}

        applied = _write_ai_grading_result(
            biz,
            submission_id=submission_id,
            expected_submission_count=submission_count,
            score=score,
            content=content,
        )
        if not applied:
            final_output = "提交版本已变化，批改结果未写回。"
            status = "stale"
        else:
            final_output = "批改完成。"
            status = "completed"
        artifacts = [{
            "artifact_type": "grading_outcome",
            "schema_version": "v1",
            "payload": {
                "score": score,
                "content": content,
                "model_code": result.get("model_code"),
            },
        }]
        agent_run.finalize_run(
            audit,
            run_id,
            user_id,
            final_output=final_output,
            artifacts=artifacts,
            usage=None,
        )
        return {"status": status, "run_id": run_id}
    except GradingRoutingError as exc:
        # 运行配置无效（缺规则模型 modelType）：
        # 模型调用前受控失败，用独立稳定错误码标记 run，不吞成 AGENT_GRADING_FAILED。
        try:
            _fail_run_with_code(audit, run_id, user_id, exc.code)
        finally:
            raise
    except SoftTimeLimitExceeded:
        # Celery 软超时：用独立错误码标记以便与普通失败区分（运营排查队列拥塞）
        try:
            _fail_run_with_code(audit, run_id, user_id, AGENT_GRADING_TIMEOUT)
        finally:
            raise
    except Exception:
        try:
            _fail_run_with_code(audit, run_id, user_id, "AGENT_GRADING_FAILED")
        finally:
            raise
    finally:
        if owns_business_db:
            biz.close()
        if owns_run_db:
            audit.close()


@celery_app.task(
    bind=True,
    name="agent.grading.run",
    acks_late=True,
    reject_on_worker_lost=True,
    # 单次模型调用超时由网关 GRADING_LLM_TIMEOUT(35s) 兜底；
    # soft_time_limit 是 worker 卡死时的最后兜底；hard limit 再留 30s 清理余量
    soft_time_limit=120,
    time_limit=150,
    # 父进程硬超时（time_limit）时，Request.on_timeout 钩子负责把 run 收口
    # 为 failed/AGENT_GRADING_TIMEOUT（子进程已被 kill，无法自行收口）
    # 承重不变量：crud.agent_run.GRADING_STALE_SECONDS(180s) 必须大于本任务的
    # time_limit(150s)，否则读取时的僵尸收口会先于父进程硬超时，把仍在跑的
    # run 误标为失败。改任一侧时必须同步核对另一侧。
    base=GradingTask,
)
def run_grading_task(
    self,
    *,
    submission_id: int,
    submission_count: int,
    rubric_version: str,
    run_id: str,
    user_id: int,
):
    return execute_grading_job(
        submission_id=submission_id,
        submission_count=submission_count,
        rubric_version=rubric_version,
        run_id=run_id,
        user_id=user_id,
    )


__all__ = [
    "GradingRoutingError",
    "build_grading_idempotency_key",
    "enqueue_grading_job",
    "execute_grading_job",
    "rubric_from_ai_rule",
    "run_grading_task",
]
