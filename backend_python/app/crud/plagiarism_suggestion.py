"""查重 AI 建议服务：确定性结果经 LangGraph 解释 + 审核后返回。

阶段 3B.4：
- 作业内容截断后以不可信块进入解释节点（submission_excerpt）。
- 图为 Explain → Review → Output，审核拒绝走安全兜底文案。
- 每次解释落一条 AgentRun/Artifact（plagiarism- 系统会话，
  与批改 grading- 会话同等隔离：不进会话列表、不可对话/取消）。
"""
import hashlib
import logging
from copy import deepcopy

from sqlalchemy.orm import Session

from ..agent.graphs.plagiarism import build_plagiarism_graph
from ..agent.subagents.plagiarism_analysis import (
    create_node as create_plagiarism_node,
)
from ..agent.subagents.plagiarism_review import (
    create_node as create_plagiarism_review_node,
)
from ..assistant_database import AssistantSessionLocal
from ..models import AgentSession
from . import agent_run, agent_session

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


def _session_id_for(submission_id: int, actor_user_id: int) -> str:
    """按提交+教师定会话：作业转交后新教师用自己的会话，不撞归属校验。"""
    digest = hashlib.sha256(
        f"plagiarism:submission:{submission_id}:teacher:{actor_user_id}"
        .encode("utf-8"),
    ).hexdigest()[:40]
    return f"plagiarism-{digest}"


def generate_plagiarism_suggestion(
    db: Session,
    student_name: str,
    student_number: str,
    content: str,
    plagiarism_info: dict,
    compare_name: str = None,
    compare_content: str = None,
    snippets: list = None,
    *,
    submission_id: int,
    actor_user_id: int,
) -> str:
    """生成查重 AI 建议并落一条解释运行。

    参数:
        db: 业务库会话（用于获取 AI 模型配置）
        student_name / student_number: 学生信息（仅日志用途）
        content: 学生作业全文文本——截断后进入解释节点的不可信块
        plagiarism_info: 查重结果字典（数值与证据在图内冻结，模型不可改）
        compare_name / compare_content: 对比模式下对方姓名与作业文本（可选）；
            对方文本同样截断后并入不可信块
        snippets: 对比模式下命中的重复片段列表（可选）
        submission_id / actor_user_id: 定位系统会话与运行归属（任课教师）

    返回:
        审核通过的解释文本；审核拒绝时为安全兜底文案
    """
    deterministic_result = deepcopy(plagiarism_info)
    if snippets:
        evidence = deterministic_result.setdefault("evidence", {})
        evidence.setdefault("common", [])
        evidence["common"].extend(
            {"snippet": snippet}
            for snippet in snippets[:10]
        )

    excerpt_parts = [_truncate(content)]
    if compare_name and compare_content:
        excerpt_parts.append(
            f"[对比对象 {compare_name} 的作业内容]\n{_truncate(compare_content)}",
        )
    submission_excerpt = "\n".join(part for part in excerpt_parts if part)

    graph = build_plagiarism_graph(
        create_plagiarism_node(db),
        create_plagiarism_review_node(db),
    )

    # 会话/运行落 PostgreSQL：与批改任务同为「业务触发的系统运行」，
    # 是双库交汇点之一（对照 tasks/grading.py）
    with AssistantSessionLocal() as sdb:
        session_id = _session_id_for(submission_id, actor_user_id)
        if sdb.query(AgentSession).filter(
            AgentSession.id == session_id,
        ).first() is None:
            agent_session.create_session(
                sdb,
                user_id=actor_user_id,
                actor_role="teacher",
                session_id=session_id,
                title="查重解释",
            )
        run = agent_run.create_run(
            sdb,
            session_id=session_id,
            user_id=actor_user_id,
            intent="plagiarism_explain",
            graph_version="plagiarism-v2",
        )
        try:
            analysis = graph.invoke({
                "deterministic_result": deterministic_result,
                "submission_excerpt": submission_excerpt,
            })["analysis"]
        except Exception:
            agent_run.fail_run(
                sdb, run.id, actor_user_id, "AGENT_PLAGIARISM_FAILED",
            )
            raise

        suggestions = "\n".join(
            f"- {item}"
            for item in analysis.explanation.review_suggestions
        )
        text = (
            f"{analysis.explanation.explanation}\n\n人工核查建议：\n{suggestions}"
            if suggestions
            else analysis.explanation.explanation
        )
        agent_run.finalize_run(
            sdb,
            run.id,
            actor_user_id,
            final_output=text,
            artifacts=[{
                "artifact_type": "plagiarism_analysis",
                "schema_version": analysis.schema_version,
                "payload": analysis.model_dump(mode="json"),
            }],
        )

    logger.info(
        "查重解释 Graph 完成，学生: %s, 对比模式: %s",
        student_name,
        bool(compare_name),
    )
    return text
