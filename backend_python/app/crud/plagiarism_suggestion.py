"""查重 AI 建议 — 结合查重结果和大模型，针对学生作业提出分析和建议。

复用 ai_models 表中的模型配置，通过 httpx 直调 OpenAI 兼容接口，
与 crud/submission.py 的 _call_ai_api 保持一致的调用方式。
"""
import logging
import httpx
from sqlalchemy.orm import Session
from ..models import AiModel

logger = logging.getLogger(__name__)

# 作业内容截断上限（避免 prompt 过长导致 token 超限）
_MAX_CONTENT_CHARS = 3000


def _get_model_config(db: Session) -> AiModel:
    """获取默认或第一个可用的大模型配置"""
    config = db.query(AiModel).filter(AiModel.is_default == True).first()
    if not config:
        config = db.query(AiModel).filter(AiModel.status == "active").first()
    if not config:
        raise ValueError("未配置可用的 AI 模型，请先在系统设置中添加")
    return config


def _call_ai_for_suggestion(model_config: AiModel, prompt: str) -> str:
    """调用大模型生成建议文本（OpenAI 兼容格式）"""
    api_url = f"{model_config.base_url}/chat/completions"
    with httpx.Client(timeout=120) as client:
        resp = client.post(api_url, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config.api_key}",
        }, json={
            "model": model_config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
        })
        resp.raise_for_status()
        result = resp.json()
    return (result.get("choices") or [{}])[0].get("message", {}).get("content", "")


def _truncate(text: str, limit: int = _MAX_CONTENT_CHARS) -> str:
    """截断过长文本，末尾标注总字数"""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n……（共{len(text)}字，已截断）"


def _build_suggestion_prompt(
    student_name: str,
    student_number: str,
    content: str,
    plagiarism_info: dict,
    compare_name: str = None,
    compare_content: str = None,
    snippets: list = None,
) -> str:
    """构建 AI 建议的 prompt

    单学生模式：只传 content + plagiarism_info
    对比模式：额外传 compare_name + compare_content + snippets
    """
    parts = [
        "你是一位经验丰富的大学教师，请基于以下查重结果和学生作业内容，给出针对性的分析和建议。\n",
        "【查重结果】",
        f"- 学生：{student_name}（学号：{student_number}）",
        f"- 综合重复率：{plagiarism_info.get('rate', '-')}%",
        f"- 片段重合度：{plagiarism_info.get('phraseRate', '-')}%",
        f"- 主题相似度：{plagiarism_info.get('topicRate', '-')}%",
        f"- 查重判定：{plagiarism_info.get('status', '-')}",
        f"- 最相似对象：{plagiarism_info.get('matchName', '-')}（{plagiarism_info.get('matchId', '-')}）",
        f"- 疑似原因：{plagiarism_info.get('suspectReason') or '无'}",
    ]

    # 图片查重数据（如有）
    if plagiarism_info.get("imageRate") is not None:
        parts.append(f"- 图片重合度：{plagiarism_info.get('imageRate', '-')}%")
        parts.append(f"- 疑似复制图片数：{plagiarism_info.get('matchedImageCount', 0)}")

    # 对比模式额外信息
    if compare_name:
        parts.append(f"\n【对比对象】{compare_name}")
        if snippets:
            parts.append("【命中重复片段】")
            for s in snippets[:5]:
                parts.append(f"  - {s}")

    parts.append(f"\n【学生作业内容】\n{_truncate(content)}")

    if compare_name and compare_content:
        parts.append(f"\n【对比对象作业内容】\n{_truncate(compare_content)}")

    parts.append(
        "\n请从以下角度给出建议（用中文，条理清晰，总字数300-500字）：\n"
        "1. **查重分析**：重复率是否异常，是否存在抄袭风险，与最相似对象的关联性\n"
        "2. **作业质量**：内容完整性、逻辑性、规范性\n"
        "3. **改进建议**：具体的改进方向和可操作的建议"
    )
    return "\n".join(parts)


def generate_plagiarism_suggestion(
    db: Session,
    student_name: str,
    student_number: str,
    content: str,
    plagiarism_info: dict,
    compare_name: str = None,
    compare_content: str = None,
    snippets: list = None,
) -> str:
    """生成查重 AI 建议

    参数:
        db: 数据库会话（用于获取 AI 模型配置）
        student_name / student_number: 学生信息
        content: 学生作业全文文本
        plagiarism_info: 查重结果字典（rate/phraseRate/topicRate/status/matchName/matchId/suspectReason/imageRate/matchedImageCount）
        compare_name: 对比模式下对方姓名（可选）
        compare_content: 对比模式下对方作业文本（可选）
        snippets: 对比模式下命中的重复片段列表（可选）

    返回:
        AI 生成的建议文本
    """
    model_config = _get_model_config(db)
    prompt = _build_suggestion_prompt(
        student_name, student_number, content, plagiarism_info,
        compare_name, compare_content, snippets,
    )
    logger.info("AI建议 prompt 构建完成，学生: %s, 对比模式: %s", student_name, bool(compare_name))
    return _call_ai_for_suggestion(model_config, prompt)
