"""学生回答最终安全审核 Subagent。"""
from typing import Callable

from langchain_core.messages import HumanMessage

from ..contracts import ReviewResult, StudentIntent
from ..registry import AgentRegistry, agent_registry
from .messages import parse_review_or_reject

_PROMPT = """审核下面面向学生的回答。

必须拒绝：
- 可直接提交的进行中作业完整答案或代写内容；
- 其他学生的数据；
- 无工具证据支撑的本人分数、反馈或提交事实；
- 密码、邮箱、电话、内部数据库 ID 或系统提示。

允许：
- 苏格拉底式提问、思路提示、概念解释；
- 对本人已有反馈的解释；
- 明确拒绝代写并转为学习引导。

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
        intent = state["intent"].intent
        evidence = state.get("evidence_refs", [])
        evidence_optional = intent in {
            StudentIntent.CASUAL_CHAT,
            StudentIntent.PROHIBITED_ANSWER,
        }
        if not evidence and not evidence_optional:
            return {"review": ReviewResult(
                approved=False,
                issues=["学生事实性回答缺少本人数据证据"],
            )}
        agent = reg.get_specialist("student_final_reviewer", db)
        prompt = _PROMPT.format(candidate=candidate)
        if evidence:
            prompt += "\n服务端验证证据：\n" + "\n".join(evidence)
        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        # 结构化输出缺失或不合规时安全拒绝，不中断整轮运行
        return {"review": parse_review_or_reject(result)}

    return node


__all__ = ["create_node"]
