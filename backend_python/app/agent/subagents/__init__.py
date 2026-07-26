"""教师端 Subagent 节点容器。

SubagentContainer 组合三个 Subagent 节点函数，供 build_teacher_graph 使用。
每个节点通过 SpecialistRegistry 获取真实 Agent（带缓存）。
"""
from sqlalchemy.orm import Session
from ...assistant_database import AssistantSessionLocal
from ...crud.agent_approval import create_approval

from ..registry import AgentRegistry
from . import (
    final_reviewer,
    grading,
    grading_review,
    plagiarism_analysis,
    learning_coach,
    feedback_explainer,
    learning_planner,
    student_final_reviewer,
    operations_analysis,
    audit_analysis,
    model_governance,
    admin_final_reviewer,
    teacher_data,
    teacher_strategy,
)


class SubagentContainer:
    """组合三个 specialist 节点，供 LangGraph 调用。

    用法：
        specialists = SpecialistContainer(db)
        graph = build_teacher_graph(specialists)
    """

    def __init__(self, db: Session, registry: AgentRegistry | None = None) -> None:
        self._teaching_data = teacher_data.create_node(db, registry)
        self._teaching_strategy = teacher_strategy.create_node(db, registry)
        self._final_reviewer = final_reviewer.create_node(db, registry)

    def teaching_data(self, state: dict) -> dict:
        return self._teaching_data(state)

    def teaching_strategy(self, state: dict) -> dict:
        return self._teaching_strategy(state)

    def final_reviewer(self, state: dict) -> dict:
        return self._final_reviewer(state)


class StudentSubagentContainer:
    """组合学生端三个专业 Agent 和最终审核 Agent。"""

    def __init__(self, db: Session, registry: AgentRegistry | None = None) -> None:
        self._learning_coach = learning_coach.create_node(db, registry)
        self._feedback_explainer = feedback_explainer.create_node(db, registry)
        self._learning_planner = learning_planner.create_node(db, registry)
        self._final_reviewer = student_final_reviewer.create_node(db, registry)

    def learning_coach(self, state: dict) -> dict:
        return self._learning_coach(state)

    def feedback_explainer(self, state: dict) -> dict:
        return self._feedback_explainer(state)

    def learning_planner(self, state: dict) -> dict:
        return self._learning_planner(state)

    def final_reviewer(self, state: dict) -> dict:
        return self._final_reviewer(state)


class AdminSubagentContainer:
    """组合管理员端运营、审计、模型治理和最终审核 Agent。"""

    def __init__(self, db: Session, registry: AgentRegistry | None = None) -> None:
        self._operations_analysis = operations_analysis.create_node(db, registry)
        self._audit_analysis = audit_analysis.create_node(db, registry)
        self._model_governance = model_governance.create_node(db, registry)
        self._final_reviewer = admin_final_reviewer.create_node(db, registry)

    def operations_analysis(self, state: dict) -> dict:
        return self._operations_analysis(state)

    def audit_analysis(self, state: dict) -> dict:
        return self._audit_analysis(state)

    def model_governance(self, state: dict) -> dict:
        return self._model_governance(state)

    def final_reviewer(self, state: dict) -> dict:
        return self._final_reviewer(state)

    def persist_approval(self, state: dict) -> dict:
        draft = state.get("action_draft")
        if draft is None:
            return {}
        with AssistantSessionLocal() as sdb:
            approval = create_approval(
                sdb,
                draft=draft,
                requester_user_id=state["actor"].user_id,
                requester_role="superadmin",
                run_id=state.get("run_id"),
            )
            return {"approval_id": approval.id}


__all__ = [
    "SubagentContainer",
    "teacher_data",
    "teacher_strategy",
    "final_reviewer",
    "grading",
    "grading_review",
    "plagiarism_analysis",
    "learning_coach",
    "feedback_explainer",
    "learning_planner",
    "student_final_reviewer",
    "StudentSubagentContainer",
    "operations_analysis",
    "audit_analysis",
    "model_governance",
    "admin_final_reviewer",
    "AdminSubagentContainer",
]
