"""教师写操作 Subagent 与审批落库（规划阶段 3A.1）。

安全不变式：
- 提案里的身份/凭据字段一律拒绝。
- 旧值快照只能来自数据库，不能采信模型给的值。
- 归属校验在图内先做一道，非本人作业不产出草案。
- 节点只构造草案，不落审批、不写业务库。
"""
import json
from datetime import datetime, timedelta

import pytest
from langchain_core.messages import ToolMessage
from pydantic import ValidationError

from app.agent.contracts import (
    ActorContext,
    IntentDecision,
    TeacherActionProposal,
    TeacherIntent,
)
from app.agent.subagents import SubagentContainer, teacher_action
from app.models import AgentApproval, Assignment, Class


class _Agent:
    def __init__(self, structured, messages=None):
        self.structured = structured
        self.messages = messages or []
        self.contexts = []

    def invoke(self, payload, context=None):
        self.contexts.append(context)
        return {
            "structured_response": self.structured,
            "messages": self.messages,
        }


class _Registry:
    def __init__(self, agent):
        self.agent = agent

    def get_specialist(self, name, db):
        assert name == "teacher_action"
        return self.agent


@pytest.fixture()
def owned_assignment(db, teacher):
    klass = Class(name="草案班", code="DRAFTCLS", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    assignment = Assignment(
        title="第三章作业",
        description="库里的真实描述",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(klass.id), "name": klass.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="draft",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def _state(teacher_id, run_id="run-1"):
    return {
        "actor": ActorContext(
            user_id=teacher_id,
            role="teacher",
            request_id="req-1",
            session_id="session-1",
        ),
        "user_message": "帮我发布第三章作业",
        "recent_messages": [],
        "run_id": run_id,
        "intent": IntentDecision(
            intent=TeacherIntent.ACTION_DRAFT,
            target_agent="teacher_action_agent",
        ),
    }


def _response(action_type, parameters, answer="已准备草案"):
    return {
        "answer": answer,
        "evidence_refs": ["mysql://assignment/7"],
        "limitations": [],
        "proposal": {
            "action_type": action_type,
            "target_id": None,
            "parameters": parameters,
            "summary": "发布《第三章作业》",
        },
    }


def _tool_evidence():
    return [ToolMessage(
        content=json.dumps({"evidence_refs": ["mysql://assignment/7"]}),
        tool_call_id="call-1",
    )]


# ========== 契约层 ==========

@pytest.mark.parametrize("field", [
    "teacherId", "teacher_id", "userId", "role", "createdBy", "apiKey",
])
def test_proposal_rejects_identity_or_credential_fields(field):
    with pytest.raises(ValidationError, match="身份或凭据"):
        TeacherActionProposal(
            action_type="update_assignment",
            parameters={"assignmentId": 7, field: "x"},
            summary="试图提权",
        )


def test_proposal_rejects_admin_only_action():
    with pytest.raises(ValidationError):
        TeacherActionProposal(
            action_type="update_model_config",
            parameters={"code": "deepseek"},
            summary="教师不能提案模型配置",
        )


def test_proposal_rejects_empty_parameters():
    with pytest.raises(ValidationError, match="参数不能为空"):
        TeacherActionProposal(
            action_type="delete_assignment",
            parameters={},
            summary="空参数",
        )


# ========== 节点：草案构造 ==========

def test_proposal_creates_draft_without_persisting(db, teacher, owned_assignment):
    agent = _Agent(
        _response("publish_assignment", {"assignmentId": owned_assignment.id}),
        messages=_tool_evidence(),
    )
    node = teacher_action.create_node(db, _Registry(agent))

    update = node(_state(teacher.id))

    draft = update["action_draft"]
    assert draft.action_type.value == "publish_assignment"
    assert draft.target_type == "assignment"
    assert draft.target_id == str(owned_assignment.id)
    assert draft.risk_level.value == "high"
    assert "approval_id" not in update


def test_target_id_is_derived_from_payload_not_from_model(
    db, teacher, owned_assignment,
):
    """模型给的 target_id 不可信，服务端一律从 parameters 推导。"""
    response = _response(
        "delete_assignment", {"assignmentId": owned_assignment.id},
    )
    response["proposal"]["target_id"] = "999999"
    node = teacher_action.create_node(
        db, _Registry(_Agent(response, messages=_tool_evidence())),
    )

    update = node(_state(teacher.id))

    assert update["action_draft"].target_id == str(owned_assignment.id)


def test_snapshot_comes_from_database_not_from_model(
    db, teacher, owned_assignment,
):
    agent = _Agent(
        _response("update_assignment", {
            "assignmentId": owned_assignment.id,
            "changes": {"description": "模型想改成这样"},
            "beforeSnapshot": {"description": "模型伪造的旧值"},
        }),
        messages=_tool_evidence(),
    )
    node = teacher_action.create_node(db, _Registry(agent))

    update = node(_state(teacher.id))

    snapshot = update["action_draft"].parameters["beforeSnapshot"]
    assert snapshot["description"] == "库里的真实描述"
    assert snapshot["title"] == "第三章作业"
    assert snapshot["status"] == "draft"


def test_foreign_assignment_produces_no_draft(db, teacher, user_factory):
    other = user_factory("t_draft_other", "teacher")
    foreign = Assignment(
        title="别人的作业",
        teacher_id=other.id,
        teacher_name=other.name,
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="draft",
    )
    db.add(foreign)
    db.commit()
    node = teacher_action.create_node(
        db,
        _Registry(_Agent(
            _response("delete_assignment", {"assignmentId": foreign.id}),
            messages=_tool_evidence(),
        )),
    )

    update = node(_state(teacher.id))

    assert "action_draft" not in update
    assert any("作业" in item for item in update["limitations"])


def test_missing_structured_response_degrades_safely(db, teacher):
    node = teacher_action.create_node(db, _Registry(_Agent(None)))

    update = node(_state(teacher.id))

    assert "action_draft" not in update
    assert update["candidate_answer"] == ""


def test_idempotency_seed_binds_draft_to_run(db, teacher, owned_assignment):
    def build(run_id):
        node = teacher_action.create_node(
            db,
            _Registry(_Agent(
                _response("publish_assignment", {
                    "assignmentId": owned_assignment.id,
                }),
                messages=_tool_evidence(),
            )),
        )
        return node(_state(teacher.id, run_id=run_id))["action_draft"]

    assert build("run-1").idempotency_key == build("run-1").idempotency_key
    assert build("run-1").idempotency_key != build("run-2").idempotency_key


# ========== 容器：落审批 ==========

def test_persist_approval_writes_teacher_owned_pending_record(
    db, teacher, assistant_db, owned_assignment,
):
    node = teacher_action.create_node(
        db,
        _Registry(_Agent(
            _response("publish_assignment", {
                "assignmentId": owned_assignment.id,
            }),
            messages=_tool_evidence(),
        )),
    )
    state = _state(teacher.id)
    state.update(node(state))
    container = SubagentContainer.__new__(SubagentContainer)

    result = container.persist_approval(state)

    assert result["approval_id"]
    assistant_db.expire_all()
    approval = assistant_db.query(AgentApproval).one()
    assert approval.requester_user_id == teacher.id
    assert approval.requester_role == "teacher"
    assert approval.status == "pending"
    assert approval.action_type == "publish_assignment"


def test_persist_approval_is_noop_without_draft():
    container = SubagentContainer.__new__(SubagentContainer)

    assert container.persist_approval({"action_draft": None}) == {}
