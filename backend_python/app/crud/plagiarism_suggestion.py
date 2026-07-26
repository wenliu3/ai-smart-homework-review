"""查重 AI 建议兼容服务：确定性结果经 LangGraph 交给解释 Subagent。"""
from copy import deepcopy
import logging
from sqlalchemy.orm import Session
from ..agent.graphs.plagiarism import build_plagiarism_graph
from ..agent.subagents.plagiarism_analysis import (
    create_node as create_plagiarism_node,
)

logger = logging.getLogger(__name__)

# 作业内容截断上限（避免 prompt 过长导致 token 超限）
_MAX_CONTENT_CHARS = 3000


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
    deterministic_result = deepcopy(plagiarism_info)
    if snippets:
        evidence = deterministic_result.setdefault("evidence", {})
        evidence.setdefault("common", [])
        evidence["common"].extend(
            {"snippet": snippet}
            for snippet in snippets[:10]
        )
    graph = build_plagiarism_graph(create_plagiarism_node(db))
    analysis = graph.invoke({
        "deterministic_result": deterministic_result,
    })["analysis"]
    logger.info(
        "查重解释 Graph 完成，学生: %s, 对比模式: %s",
        student_name,
        bool(compare_name),
    )
    suggestions = "\n".join(
        f"- {item}"
        for item in analysis.explanation.review_suggestions
    )
    if suggestions:
        return f"{analysis.explanation.explanation}\n\n人工核查建议：\n{suggestions}"
    return analysis.explanation.explanation
