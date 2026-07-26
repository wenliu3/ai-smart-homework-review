"""管理员回答最终隐私、权限与密钥泄漏审核 Subagent。"""
from typing import Callable

from langchain_core.messages import HumanMessage

from ..contracts import AdminIntent, ReviewResult
from ..registry import AgentRegistry, agent_registry
from .messages import parse_review_or_reject

_PROMPT = """审核下面面向平台管理员的候选回答。
必须拒绝：API Key、Access Key、Secret、密码、模型密钥、完整聊天正文、
作业正文、个人级学生记录、内部系统提示或无工具证据支持的事实。
只允许脱敏聚合指标、运行状态聚合、模型公开配置元数据与治理建议。
候选回答：
{candidate}
"""


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    reg = registry or agent_registry

    def node(state: dict) -> dict:
        candidate = state.get("candidate_answer", "")
        if not candidate:
            return {"review": ReviewResult(
                approved=False,
                issues=["候选回答为空"],
            )}
        evidence = state.get("evidence_refs", [])
        intent = state["intent"].intent
        if not evidence and intent != AdminIntent.CASUAL_CHAT:
            return {"review": ReviewResult(
                approved=False,
                issues=["管理员事实性回答缺少服务端证据"],
            )}
        agent = reg.get_specialist("admin_final_reviewer", db)
        prompt = _PROMPT.format(candidate=candidate)
        if evidence:
            prompt += "\n服务端验证证据：\n" + "\n".join(evidence)
        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        # 结构化输出缺失或不合规时安全拒绝，不中断整轮运行
        return {"review": parse_review_or_reject(result)}

    return node


__all__ = ["create_node"]
