"""作业生命周期审批动作的 HTTP 全链路（规划阶段 3A.2）。

建草案 → 审批执行 → 幂等重放，以及篡改/越权在 API 层的表现。
"""
from datetime import datetime, timedelta

import pytest

from app.models import Assignment, Class


@pytest.fixture()
def draft_assignment(db, teacher):
    """一份 draft 状态、已关联自有班级的作业。"""
    klass = Class(name="接口班", code="APICLS", teacher_id=teacher.id)
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


def _create_draft(client, headers, action_type, assignment_id, **parameters):
    payload = {"assignmentId": assignment_id, **parameters}
    return client.post(
        "/api/assistant/approvals",
        headers=headers,
        json={
            "actionType": action_type,
            "targetType": "assignment",
            "targetId": str(assignment_id),
            "parameters": payload,
            "summary": f"{action_type} 作业 {assignment_id}",
            "riskLevel": "high",
        },
    )


def test_publish_assignment_end_to_end_and_replay(
    client, db, teacher, auth_header, draft_assignment,
):
    headers = auth_header(teacher)
    created = _create_draft(
        client, headers, "publish_assignment", draft_assignment.id,
        beforeSnapshot={"status": "draft", "title": "第三章作业"},
    )
    assert created.status_code == 200
    approval = created.json()["data"]
    assert approval["status"] == "pending"
    assert approval["riskLevel"] == "high"

    approved = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 200
    result = approved.json()["data"]["result"]
    assert result["success"] is True

    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first().status == "published"

    replay = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["result"] == result


def test_update_assignment_applies_only_whitelisted_changes(
    client, db, teacher, auth_header, draft_assignment,
):
    headers = auth_header(teacher)
    created = _create_draft(
        client, headers, "update_assignment", draft_assignment.id,
        changes={"title": "第三章作业（修订）"},
        beforeSnapshot={"title": "第三章作业"},
    )
    approval = created.json()["data"]

    approved = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 200

    db.expire_all()
    row = db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first()
    assert row.title == "第三章作业（修订）"
    # 状态与描述不在本次变更内，必须原样保留
    assert row.status == "draft"
    assert row.description == "原始描述"


def test_delete_assignment_soft_deletes_via_api(
    client, db, teacher, auth_header, draft_assignment,
):
    headers = auth_header(teacher)
    created = _create_draft(
        client, headers, "delete_assignment", draft_assignment.id,
        beforeSnapshot={"title": "第三章作业", "status": "draft"},
    )
    approval = created.json()["data"]

    approved = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 200

    db.expire_all()
    row = db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first()
    assert row is not None
    assert row.deleted_at is not None


def test_update_with_unauthorized_field_is_rejected(
    client, teacher, auth_header, draft_assignment,
):
    headers = auth_header(teacher)
    created = _create_draft(
        client, headers, "update_assignment", draft_assignment.id,
        changes={"status": "published"},
    )
    approval = created.json()["data"]

    approved = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 400
    assert "字段" in approved.json()["message"]


def test_tampered_assignment_id_is_rejected(
    client, teacher, auth_header, draft_assignment,
):
    headers = auth_header(teacher)
    created = _create_draft(
        client, headers, "delete_assignment", draft_assignment.id,
    )
    approval = created.json()["data"]

    tampered = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=headers,
        json={"payload": {"assignmentId": draft_assignment.id + 1}},
    )
    assert tampered.status_code == 400
    assert "载荷" in tampered.json()["message"]


def test_another_teacher_cannot_approve_foreign_assignment_action(
    client, db, teacher, user_factory, auth_header, draft_assignment,
):
    """草案由他人作业构造时，审批阶段的对象归属复验必须拦下。"""
    other = user_factory("t_api_other", "teacher")
    other_headers = auth_header(other)

    created = _create_draft(
        client, other_headers, "delete_assignment", draft_assignment.id,
    )
    approval = created.json()["data"]

    approved = client.post(
        f"/api/assistant/approvals/{approval['approvalId']}/approve",
        headers=other_headers,
        json={"payload": approval["parameters"]},
    )
    assert approved.status_code == 400
    assert "作业" in approved.json()["message"]

    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.id == draft_assignment.id,
    ).first().deleted_at is None


def test_student_cannot_reach_approval_endpoints(client, student, auth_header):
    headers = auth_header(student)

    assert client.get(
        "/api/assistant/approvals", headers=headers,
    ).status_code == 403
    assert client.post(
        "/api/assistant/approvals",
        headers=headers,
        json={
            "actionType": "delete_assignment",
            "targetType": "assignment",
            "targetId": "1",
            "parameters": {"assignmentId": 1},
            "summary": "越权删除",
            "riskLevel": "high",
        },
    ).status_code == 403
