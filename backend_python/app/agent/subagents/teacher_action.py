"""教师写操作 Subagent：只构造待审批草案，不执行任何业务写入。

安全设计：
- 提案的 target_id 由服务端从 parameters 推导，不采信模型给的值。
- 旧值快照（beforeSnapshot，决策 D2）只从数据库读，用独立 Session
  以适配 LangGraph 后台线程（pymysql 连接非线程安全）。
- 归属校验在此做第一道闸；审批执行前 crud.action_execution 还会再复验一次。
"""
from typing import Callable

from ...crud.action_execution import validate_action_permission
from ...database import SessionLocal
from ...models import Assignment
from ..contracts import TeacherActionResponse
from ..registry import AgentRegistry, agent_registry
from ..tools.approval import create_action_draft
from ..tools.common import TeacherContext
from .messages import (
    build_specialist_messages,
    collect_invoke_usage,
    degraded_specialist_update,
    parse_specialist_response,
    verify_specialist_evidence,
)

# 每个动作定位对象所用的 parameters 键；与 crud/agent_approval.py
# 的 _validate_target_metadata 必须保持一致
_TARGET_SPECS = {
    "create_assignment_draft": ("assignment", None),
    "create_ai_rule": ("ai_rule", None),
    "submit_teacher_score": ("submission", "submissionId"),
    "publish_assignment": ("assignment", "assignmentId"),
    "update_assignment": ("assignment", "assignmentId"),
    "delete_assignment": ("assignment", "assignmentId"),
}

# 新建类动作风险较低（不影响既有对象），其余一律高风险
_MEDIUM_RISK_ACTIONS = frozenset({"create_assignment_draft", "create_ai_rule"})

# 作用于既有作业的动作，需要先做归属校验并冻结旧值快照
_ASSIGNMENT_ACTIONS = frozenset({
    "publish_assignment",
    "update_assignment",
    "delete_assignment",
})

# 快照字段白名单：只放审批界面做 diff 需要的业务字段
_SNAPSHOT_FIELDS = (
    "title",
    "description",
    "status",
    "allowAttachments",
)

# 创建作业草案可接受的参数白名单：与 assignment_crud.create_assignment() 对齐，
# 且与权限校验一致——validate_action_permission 要求 classes 为归属班级 ID 列表。
# 刻意排除 aiRule/attachments（Agent 无法校验的复杂字段），避免审批执行阶段才失败。
_CREATE_ASSIGNMENT_DRAFT_FIELDS = (
    "title",
    "description",
    "classes",
    "startDate",
    "endDate",
    "allowAttachments",
)

DRAFT_REJECTED_LIMITATION = "提案指向的作业不存在或不属于当前教师，已丢弃该草案"
DRAFT_INVALID_LIMITATION = "提案参数不完整，未能生成可审批的操作草案"


def _load_assignment_snapshot(assignment_id: int, teacher_id: int) -> dict | None:
    """读取旧值快照；作业不存在、已软删或不属于该教师时返回 None。"""
    with SessionLocal() as db:
        assignment = db.query(Assignment).filter(
            Assignment.alive(),
            Assignment.id == assignment_id,
        ).first()
        if assignment is None or assignment.teacher_id != teacher_id:
            return None
        record = assignment.to_dict()
        snapshot = {
            field: record.get(field)
            for field in _SNAPSHOT_FIELDS
            if field in record
        }
        snapshot["classes"] = [
            item.get("name")
            for item in (assignment.classes or [])
            if isinstance(item, dict)
        ]
        return snapshot


def _build_draft(proposal, teacher_id: int, run_id: str, db=None):
    """把模型提案转成服务端签名草案；不合法时返回 (None, 原因)。"""
    action_type = proposal.action_type
    target_type, target_key = _TARGET_SPECS[action_type]
    parameters = dict(proposal.parameters)
    # 快照由服务端重建，模型给的同名键一律丢弃
    parameters.pop("beforeSnapshot", None)

    # 创建作业草案：只投影白名单字段，且必须有 title 与归属班级列表。
    # 班级列表的归属校验复用审批执行时的同一套权限检查，避免生成后到执行阶段才失败。
    if action_type == "create_assignment_draft":
        parameters = {
            key: parameters[key]
            for key in _CREATE_ASSIGNMENT_DRAFT_FIELDS
            if key in parameters
        }
        if not parameters.get("title") or not parameters.get("classes"):
            return None, DRAFT_INVALID_LIMITATION
        if db is not None:
            try:
                validate_action_permission(
                    "create_assignment_draft",
                    parameters,
                    teacher_id,
                    "teacher",
                    db,
                )
            except ValueError:
                return None, DRAFT_REJECTED_LIMITATION

    target_id = None
    if target_key is not None:
        raw_target = parameters.get(target_key)
        if raw_target is None:
            return None, DRAFT_INVALID_LIMITATION
        target_id = str(raw_target)

    if action_type in _ASSIGNMENT_ACTIONS:
        try:
            assignment_id = int(parameters["assignmentId"])
        except (KeyError, TypeError, ValueError):
            return None, DRAFT_INVALID_LIMITATION
        snapshot = _load_assignment_snapshot(assignment_id, teacher_id)
        if snapshot is None:
            return None, DRAFT_REJECTED_LIMITATION
        parameters["assignmentId"] = assignment_id
        parameters["beforeSnapshot"] = snapshot
        target_id = str(assignment_id)

    try:
        draft = create_action_draft(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            parameters=parameters,
            summary=proposal.summary,
            risk_level=(
                "medium" if action_type in _MEDIUM_RISK_ACTIONS else "high"
            ),
            idempotency_seed=f"teacher:{teacher_id}:{run_id}",
        )
    except ValueError:
        return None, DRAFT_INVALID_LIMITATION
    return draft, None


def create_node(
    db,
    registry: AgentRegistry | None = None,
) -> Callable:
    reg = registry or agent_registry

    def node(state: dict) -> dict:
        agent = reg.get_specialist("teacher_action", db)
        result = agent.invoke(
            {"messages": build_specialist_messages(state)},
            context=TeacherContext(
                teacher_id=state["actor"].user_id,
                budget=state.get("runtime_budget"),
            ),
        )
        response = parse_specialist_response(result, TeacherActionResponse)
        if response is None:
            return {
                **degraded_specialist_update(),
                "usage": collect_invoke_usage(result),
            }
        response = verify_specialist_evidence(response, result)
        update = {
            "usage": collect_invoke_usage(result),
            "candidate_answer": response.answer,
            "evidence_refs": response.evidence_refs,
            "limitations": response.limitations,
            "specialist_response": response,
        }
        if response.proposal is None:
            return update
        draft, rejection = _build_draft(
            response.proposal,
            teacher_id=state["actor"].user_id,
            run_id=state.get("run_id", ""),
            db=db,
        )
        if draft is None:
            update["limitations"] = [*response.limitations, rejection]
            return update
        update["action_draft"] = draft
        return update

    return node


__all__ = ["create_node"]
