"""最终审核 Subagent 节点（规格 7.3 / 20）。

职责：审核 specialist 的候选回答是否安全、准确、合规。
不持有任何工具，不能自行查询数据。

审核逻辑：
- 第一次拒绝时允许修订一次（由图路由处理回退）。
- 第二次拒绝时安全降级（由图路由处理）。
- 本节点只负责产出 ReviewResult，不负责路由。
"""
from typing import Callable

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from ..contracts import ReviewResult, TeacherIntent
from ..registry import AgentRegistry, agent_registry
from ..tools.common import TeacherContext

# 安全审核 Prompt（注入到 LLM 输入）
_REVIEW_TEMPLATE = """请审核以下候选回答是否安全合规。

候选回答：
{candidate}

审核要点：
1. 不包含密码、邮箱、电话、API Key、内部数据库 ID 等敏感信息。
2. 不包含未由工具数据支撑的编造内容。
3. 不包含或暗示可以执行写操作（发布、修改、删除、改分等）。
4. 不泄露其他教师或学生的数据。

请返回 JSON 格式：
- 如果通过：{{"approved": true, "issues": []}}
- 如果拒绝：{{"approved": false, "issues": ["具体问题1", "具体问题2"]}}
"""


def _structured_review_or_reject(result: dict) -> ReviewResult:
    """读取 LangChain v1 结构化输出；缺失或校验失败时安全拒绝。"""
    try:
        structured = result["structured_response"]
        return ReviewResult.model_validate(structured, strict=True)
    except (KeyError, TypeError, ValidationError):
        return ReviewResult(
            approved=False,
            issues=["审核模型未返回有效的结构化结果"],
        )


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    """创建最终审核节点函数（闭包捕获 db 和 registry）。"""
    reg = registry or agent_registry

    def final_reviewer_node(state: dict) -> dict:
        candidate = state.get("candidate_answer", "")
        if not candidate:
            return {"review": ReviewResult(approved=False, issues=["候选回答为空"])}
        evidence_refs = state.get("evidence_refs", [])
        intent = state.get("intent")
        is_casual = (
            intent is not None
            and intent.intent == TeacherIntent.CASUAL_CHAT
        )
        if not evidence_refs and not is_casual:
            return {"review": ReviewResult(
                approved=False,
                issues=["事实性回答缺少可核验的证据引用"],
            )}
        actor = state["actor"]
        agent = reg.get_specialist("final_reviewer", db)
        prompt = _REVIEW_TEMPLATE.format(candidate=candidate)
        if evidence_refs:
            prompt += "\n服务端证据引用：\n" + "\n".join(evidence_refs)
        result = agent.invoke(
            {"messages": [HumanMessage(content=prompt)]},
            context=TeacherContext(
                teacher_id=actor.user_id,
                budget=state.get("runtime_budget"),
            ),
        )
        review = _structured_review_or_reject(result)
        return {"review": review}

    return final_reviewer_node


def build_final_reviewer_agent(db, registry: AgentRegistry | None = None) -> Callable:
    """构建最终审核 Subagent 节点。"""
    return create_node(db, registry)


__all__ = ["build_final_reviewer_agent", "create_node"]
