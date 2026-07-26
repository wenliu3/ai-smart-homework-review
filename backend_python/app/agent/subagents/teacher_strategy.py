"""教师策略 Subagent 节点（规格 7.2 / 20）。

职责：调用 teaching_strategy Agent 基于工具数据生成教学策略建议，
返回候选回答供 final_reviewer 审核。

与 teaching_data 的区别：Prompt 强调策略建议而非数据陈述，
但共享同一组只读工具和 general Profile 模型。
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
    """创建教学策略节点函数（闭包捕获 db 和 registry）。"""
    reg = registry or agent_registry

    def teaching_strategy_node(state: dict) -> dict:
        actor = state["actor"]
        agent = reg.get_specialist("teaching_strategy", db)
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

    return teaching_strategy_node


def build_teacher_strategy_agent(db, registry: AgentRegistry | None = None) -> Callable:
    """构建教师策略 Subagent 节点。"""
    return create_node(db, registry)


__all__ = ["build_teacher_strategy_agent", "create_node"]
