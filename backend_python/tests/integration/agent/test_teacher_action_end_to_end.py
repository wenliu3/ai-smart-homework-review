"""阶段 3A 验收：教师写操作全链路。

教师聊天 → 写操作 Agent 产出草案 → 审核通过落审批 → approval.required 事件
→ 教师在审批接口看到字段级 diff 所需的旧值快照 → 批准 → 业务库落地。

外部依赖只替换模型本身（FakeRegistry），草案构造、快照采集、审批落库、
载荷复验与业务执行全部走真实代码。
"""
import json
from datetime import datetime, timedelta

import pytest
from langchain_core.messages import ToolMessage

from app.agent.contracts import ReviewResult
from app.agent.service import orchestrate_teacher_run
from app.agent.subagents import SubagentContainer, teacher_action
from app.crud.agent_session import create_session
from app.models import Assignment, Class


class _Agent:
    """返回固定结构化提案的模型替身。"""

    def __init__(self, structured):
        self.structured = structured

    def invoke(self, payload, context=None):
        return {
            "structured_response": self.structured,
            "messages": [ToolMessage(
                content=json.dumps({"evidence_refs": ["mysql://assignment"]}),
                tool_call_id="call-1",
            )],
        }


class _Registry:
    def __init__(self, agent):
        self.agent = agent

    def get_specialist(self, name, db):
        return self.agent


class _ChainSpecialists(SubagentContainer):
    """真实写操作节点 + 真实落审批；只把模型与最终审核换成替身。"""

    def __init__(self, db, registry):
        self._action_draft = teacher_action.create_node(db, registry)

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


@pytest.fixture()
def draft_assignment(db, teacher):
    klass = Class(name="全链路班", code="E2ECLS", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    assignment = Assignment(
        title="第三章作业",
        description="原始描述",
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


def _run_chat(db, assistant_db, teacher, structured, session_suffix):
    session = create_session(
        assistant_db,
        user_id=teacher.id,
        actor_role="teacher",
        session_id=f"e2eaction{session_suffix}",
    )
    emitted = []
    result = orchestrate_teacher_run(
        teacher_id=teacher.id,
        message="帮我发布第三章作业",
        session_id=session.id,
        request_id=f"req-e2e-{session_suffix}",
        specialists=_ChainSpecialists(db, _Registry(_Agent(structured))),
        assistant_db=assistant_db,
        event_callback=emitted.append,
    )
    return result, emitted


def _publish_proposal(assignment_id):
    return {
        "answer": "我已准备发布《第三章作业》的待审批草案。",
        "evidence_refs": ["mysql://assignment"],
        "limitations": [],
        "proposal": {
            "action_type": "publish_assignment",
            "target_id": None,
            "parameters": {"assignmentId": assignment_id},
            "summary": "发布《第三章作业》",
        },
    }


def test_teacher_chat_to_business_write_full_chain(
    client, db, assistant_db, teacher, auth_header, draft_assignment,
):
    result, emitted = _run_chat(
        db, assistant_db, teacher,
        _publish_proposal(draft_assignment.id),
        "01",
    )

    # 1. 聊天以「草案已落审批」收尾，并发出 approval.required
    assert result.status == "completed"
    assert "审批" in result.final_answer
    approval_events = [
        event for event in emitted if event["type"] == "approval.required"
    ]
    assert len(approval_events) == 1
    approval_id = approval_events[0]["data"]["approval_id"]

    # 2. 教师能在审批列表里看到它，且带上做 diff 用的旧值快照
    headers = auth_header(teacher)
    listed = client.get("/api/assistant/approvals?status=pending", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert [item["approvalId"] for item in items] == [approval_id]
    approval = items[0]
    assert approval["actionType"] == "publish_assignment"
    assert approval["riskLevel"] == "high"
    assert approval["parameters"]["beforeSnapshot"] == {
        "title": "第三章作业",
        "description": "原始描述",
        "status": "draft",
        "allowAttachments": False,
        "classes": ["全链路班"],
    }

    # 3. 批准后业务库真正落地
    approved = client.post(
        f"/api/assistant/approvals/{approval_id}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["result"]["success"] is True

    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first().status == "published"


def test_chat_draft_does_not_write_business_db_before_approval(
    db, assistant_db, teacher, draft_assignment,
):
    """图内只产出草案：审批前业务库必须纹丝不动。"""
    _run_chat(
        db, assistant_db, teacher,
        _publish_proposal(draft_assignment.id),
        "02",
    )

    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first().status == "draft"


def test_foreign_assignment_proposal_never_reaches_approval(
    db, assistant_db, teacher, user_factory,
):
    """指向他人作业的提案在图内就被丢弃，不产生任何待审批记录。"""
    from app.models import AgentApproval

    other = user_factory("t_e2e_other", "teacher")
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

    result, emitted = _run_chat(
        db, assistant_db, teacher, _publish_proposal(foreign.id), "03",
    )

    assert [
        event for event in emitted if event["type"] == "approval.required"
    ] == []
    assert assistant_db.query(AgentApproval).count() == 0
    assert "草案" in result.final_answer


# ========== 三角色越权矩阵 ==========

APPROVAL_ENDPOINTS = (
    ("get", "/api/assistant/approvals", None),
    ("post", "/api/assistant/approvals", {
        "actionType": "delete_assignment",
        "targetType": "assignment",
        "targetId": "1",
        "parameters": {"assignmentId": 1},
        "summary": "越权删除",
        "riskLevel": "high",
    }),
    ("post", "/api/assistant/approvals/does-not-exist/approve", {"payload": {}}),
    ("post", "/api/assistant/approvals/does-not-exist/reject", {"reason": "no"}),
)


@pytest.mark.parametrize("method,path,body", APPROVAL_ENDPOINTS)
def test_student_is_locked_out_of_every_approval_endpoint(
    client, student, auth_header, method, path, body,
):
    response = getattr(client, method)(
        path, headers=auth_header(student), **({"json": body} if body else {}),
    )
    assert response.status_code == 403


def test_admin_cannot_approve_teacher_assignment_actions(
    client, db, user_factory, auth_header, draft_assignment,
):
    """管理员能进审批入口，但作业动作不在其角色白名单内。"""
    admin = user_factory("sa_e2e", "superadmin")
    headers = auth_header(admin)

    created = client.post(
        "/api/assistant/approvals",
        headers=headers,
        json={
            "actionType": "publish_assignment",
            "targetType": "assignment",
            "targetId": str(draft_assignment.id),
            "parameters": {"assignmentId": draft_assignment.id},
            "summary": "管理员越权发布",
            "riskLevel": "high",
        },
    )

    assert created.status_code == 400
    assert "角色" in created.json()["message"]
    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first().status == "draft"


def test_teacher_cannot_read_another_teachers_approvals(
    client, db, assistant_db, teacher, user_factory, auth_header,
    draft_assignment,
):
    _run_chat(
        db, assistant_db, teacher,
        _publish_proposal(draft_assignment.id),
        "04",
    )
    other = user_factory("t_e2e_peek", "teacher")

    listed = client.get(
        "/api/assistant/approvals", headers=auth_header(other),
    )

    assert listed.status_code == 200
    assert listed.json()["data"]["items"] == []
