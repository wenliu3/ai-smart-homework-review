"""教师数据 Subagent 节点（规格 7.1 / 20）。

职责：调用 teaching_data Agent 处理用户的数据查询请求，
返回候选回答供 final_reviewer 审核。

节点函数通过 SpecialistRegistry 获取真实 Agent（带缓存），
Agent 内部使用 general Profile 模型和只读工具集。
"""
from typing import Callable

from pydantic import ValidationError

from ..contracts import SpecialistResponse
from ..registry import AgentRegistry, agent_registry
from ..tools.common import TeacherContext
from .messages import (
    build_specialist_messages,
    collect_invoke_usage,
    verify_specialist_evidence,
)


def create_node(db, registry: AgentRegistry | None = None) -> Callable:
    """创建教学数据节点函数（闭包捕获 db 和 registry）。"""
    reg = registry or agent_registry

    def teaching_data_node(state: dict) -> dict:
        actor = state["actor"]
        agent = reg.get_specialist("teaching_data", db)
        result = agent.invoke(
            {"messages": build_specialist_messages(state)},
            context=TeacherContext(
                teacher_id=actor.user_id,
                budget=state.get("runtime_budget"),
            ),
        )
        try:
            response = SpecialistResponse.model_validate(
                result["structured_response"], strict=True,
            )
        except (KeyError, TypeError, ValidationError):
            return {
                "usage": collect_invoke_usage(result),
                "candidate_answer": "",
                "evidence_refs": [],
                "limitations": ["专业 Agent 未返回有效的结构化结果"],
                "intent": state.get("intent"),
            }
        response = verify_specialist_evidence(response, result)
        return {
            "usage": collect_invoke_usage(result),
            "candidate_answer": response.answer,
            "evidence_refs": response.evidence_refs,
            "limitations": response.limitations,
            "specialist_response": response,
            "intent": state.get("intent"),
        }

    return teaching_data_node


def build_teacher_data_agent(db, registry: AgentRegistry | None = None) -> Callable:
    """构建教师数据 Subagent 节点。"""
    return create_node(db, registry)


__all__ = ["build_teacher_data_agent", "create_node"]
