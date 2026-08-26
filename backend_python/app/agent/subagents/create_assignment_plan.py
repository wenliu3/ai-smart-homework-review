"""创建作业草稿规划 Subagent：无任何数据库工具，只产出结构化业务计划。

安全设计：
- 绑定 create_assignment_plan 专用 Agent（规格 tools=()），它没有任何数据库工具，
  LLM 无法自己查班级/作业，无法触发 get_my_assignments/get_my_assignment_summary 扇出。
- 只输出 CreateAssignmentDraftPlan（className/title/description/startDate/endDate/
  allowAttachments），班级 ID 等由服务端在 resolve_and_validate 节点解析注入。
- 身份/权限/密钥字段由 CreateAssignmentDraftPlan 的 extra="forbid" 拒绝。
"""
from typing import Callable

from pydantic import ValidationError

from ..contracts import CreateAssignmentDraftPlan
from ..registry import AgentRegistry, agent_registry
from ..tools.common import TeacherContext
from .messages import build_specialist_messages, collect_invoke_usage


def create_node(
    db,
    registry: AgentRegistry | None = None,
) -> Callable:
    reg = registry or agent_registry

    def node(state: dict) -> dict:
        agent = reg.get_specialist("create_assignment_plan", db)
        result = agent.invoke(
            {"messages": build_specialist_messages(state)},
            context=TeacherContext(
                teacher_id=state["actor"].user_id,
                budget=state.get("runtime_budget"),
            ),
        )
        plan = None
        try:
            plan = CreateAssignmentDraftPlan.model_validate(
                result["structured_response"],
                strict=False,
            )
        except (KeyError, TypeError, ValidationError):
            plan = None
        update: dict = {"usage": collect_invoke_usage(result)}
        # candidate_plan 为空时由 resolve 节点给出追问；绝不游说模型补查数据库
        update["candidate_plan"] = plan
        return update

    return node


__all__ = ["create_node"]