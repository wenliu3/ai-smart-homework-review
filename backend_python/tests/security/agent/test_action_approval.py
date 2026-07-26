from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.agent.tools.approval import create_action_draft
from app.agent.graphs.approval import build_approval_graph
from app.crud.agent_approval import (
    approve_and_execute,
    create_approval,
    reject_approval,
)
from app.crud.action_execution import (
    execute_approved_business_action,
    validate_action_permission,
)
from app.models import Assignment, Class, Submission


def _draft():
    return create_action_draft(
        action_type="create_assignment_draft",
        target_type="assignment",
        target_id=None,
        parameters={
            "title": "数据结构作业",
            "classes": [1],
        },
        summary="创建一份未发布的作业草案",
        risk_level="medium",
        ttl_seconds=600,
    )


def test_action_draft_hash_and_idempotency_are_server_generated():
    first = _draft()
    second = _draft()

    assert len(first.payload_hash) == 64
    assert len(first.idempotency_key) == 64
    assert first.payload_hash == second.payload_hash
    assert first.idempotency_key == second.idempotency_key


def test_approval_rejects_wrong_approver_tampering_and_expiry(assistant_db):
    approval = create_approval(
        assistant_db,
        draft=_draft(),
        requester_user_id=11,
        requester_role="teacher",
    )

    with pytest.raises(ValueError, match="审批人"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=12,
            actor_role="teacher",
            payload=approval.payload_json,
            executor=lambda *_: {"ok": True},
        )

    with pytest.raises(ValueError, match="载荷"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=11,
            actor_role="teacher",
            payload={**approval.payload_json, "title": "被篡改"},
            executor=lambda *_: {"ok": True},
        )

    approval.expires_at = datetime.now() - timedelta(seconds=1)
    assistant_db.commit()
    with pytest.raises(ValueError, match="过期"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=11,
            actor_role="teacher",
            payload=approval.payload_json,
            executor=lambda *_: {"ok": True},
        )


def test_approved_action_executes_exactly_once(assistant_db):
    approval = create_approval(
        assistant_db,
        draft=_draft(),
        requester_user_id=11,
        requester_role="teacher",
    )
    calls = []

    def executor(action_type, payload, idempotency_key):
        calls.append((action_type, payload, idempotency_key))
        return {"resourceId": "A-1"}

    first = approve_and_execute(
        assistant_db,
        approval_id=approval.id,
        actor_user_id=11,
        actor_role="teacher",
        payload=approval.payload_json,
        executor=executor,
    )
    second = approve_and_execute(
        assistant_db,
        approval_id=approval.id,
        actor_user_id=11,
        actor_role="teacher",
        payload=approval.payload_json,
        executor=executor,
    )

    assert first == second == {"resourceId": "A-1"}
    assert len(calls) == 1
    assert approval.status == "executed"


def test_rejected_action_can_never_execute(assistant_db):
    approval = create_approval(
        assistant_db,
        draft=_draft(),
        requester_user_id=11,
        requester_role="teacher",
    )
    reject_approval(
        assistant_db,
        approval_id=approval.id,
        actor_user_id=11,
        actor_role="teacher",
        reason="教师取消",
    )

    with pytest.raises(ValueError, match="rejected"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=11,
            actor_role="teacher",
            payload=approval.payload_json,
            executor=lambda *_: {"ok": True},
        )


def test_approval_graph_exposes_pending_approve_and_reject_nodes():
    calls = []

    class Coordinator:
        def validate(self, state):
            calls.append("validate_action_draft")
            return {}

        def persist(self, state):
            calls.append("persist_pending_approval")
            return {"approval_id": "approval-1", "status": "pending"}

        def execute(self, state):
            calls.append("execute_approved_action")
            return {"status": "executed", "result": {"ok": True}}

        def reject(self, state):
            calls.append("reject_action")
            return {"status": "rejected"}

    graph = build_approval_graph(Coordinator())
    pending = graph.invoke({"draft": _draft()})
    approved = graph.invoke({
        "approval_id": "approval-1",
        "decision": "approved",
    })
    rejected = graph.invoke({
        "approval_id": "approval-2",
        "decision": "rejected",
    })

    assert pending["status"] == "pending"
    assert approved["status"] == "executed"
    assert rejected["status"] == "rejected"
    assert calls == [
        "validate_action_draft",
        "persist_pending_approval",
        "execute_approved_action",
        "reject_action",
    ]


def test_model_config_approval_rejects_secret_or_unknown_fields():
    with pytest.raises(ValueError, match="敏感"):
        validate_action_permission(
            "update_model_config",
            {"code": "deepseek", "changes": {"apiKey": "secret"}},
            actor_user_id=1,
            actor_role="superadmin",
        )
    with pytest.raises(ValueError, match="未授权"):
        validate_action_permission(
            "update_model_config",
            {"code": "deepseek", "changes": {"totalTokens": 0}},
            actor_user_id=1,
            actor_role="superadmin",
        )


def test_reject_approval_locks_row_before_checking_pending_status():
    approval = MagicMock(
        requester_user_id=11,
        requester_role="teacher",
        status="executed",
    )
    query = MagicMock()
    query.filter.return_value = query
    query.with_for_update.return_value = query
    query.first.return_value = approval
    db = MagicMock()
    db.query.return_value = query

    with pytest.raises(ValueError, match="executed"):
        reject_approval(
            db,
            approval_id="approval-1",
            actor_user_id=11,
            actor_role="teacher",
            reason="too late",
        )

    query.with_for_update.assert_called_once_with()
    assert approval.status == "executed"
    db.commit.assert_not_called()


def test_assignment_draft_rejects_missing_or_foreign_classes(
    db, teacher, user_factory,
):
    other_teacher = user_factory("t_other", "teacher")
    owned = Class(name="owned", code="OWNED", teacher_id=teacher.id)
    foreign = Class(name="foreign", code="FOREIGN", teacher_id=other_teacher.id)
    db.add_all([owned, foreign])
    db.commit()

    with pytest.raises(ValueError, match="班级"):
        validate_action_permission(
            "create_assignment_draft",
            {"title": "draft", "classes": [owned.id, 999999]},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )
    with pytest.raises(ValueError, match="班级"):
        validate_action_permission(
            "create_assignment_draft",
            {"title": "draft", "classes": [foreign.id]},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1, 61])
def test_teacher_score_rejects_non_finite_or_out_of_range(
    db, teacher, student, score,
):
    assignment = Assignment(
        title="grading",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"maxScore": 60},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="submitted",
    )
    db.add(submission)
    db.commit()

    with pytest.raises(ValueError, match="分数"):
        validate_action_permission(
            "submit_teacher_score",
            {
                "submissionId": submission.id,
                "assignmentId": assignment.id,
                "teacherScore": score,
            },
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_teacher_score_rejects_payload_object_mismatch_and_ungradeable_status(
    db, teacher, student,
):
    assignment = Assignment(
        title="grading",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=1,
        status="draft",
    )
    db.add(submission)
    db.commit()

    with pytest.raises(ValueError, match="作业"):
        validate_action_permission(
            "submit_teacher_score",
            {
                "submissionId": submission.id,
                "assignmentId": assignment.id + 1,
                "teacherScore": 80,
            },
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )
    with pytest.raises(ValueError, match="状态"):
        validate_action_permission(
            "submit_teacher_score",
            {
                "submissionId": submission.id,
                "assignmentId": assignment.id,
                "teacherScore": 80,
            },
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_approval_target_id_must_match_score_payload(assistant_db):
    draft = create_action_draft(
        action_type="submit_teacher_score",
        target_type="submission",
        target_id="42",
        parameters={
            "submissionId": 43,
            "assignmentId": 7,
            "teacherScore": 80,
        },
        summary="grade",
        risk_level="high",
        ttl_seconds=600,
    )
    approval = create_approval(
        assistant_db,
        draft=draft,
        requester_user_id=11,
        requester_role="teacher",
    )

    with pytest.raises(ValueError, match="目标"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=11,
            actor_role="teacher",
            payload=approval.payload_json,
            executor=lambda *_: {"ok": True},
        )


def test_object_action_requires_target_id(assistant_db):
    draft = create_action_draft(
        action_type="submit_teacher_score",
        target_type="submission",
        target_id=None,
        parameters={
            "submissionId": 42,
            "assignmentId": 7,
            "teacherScore": 80,
        },
        summary="grade",
        risk_level="high",
        ttl_seconds=600,
    )
    approval = create_approval(
        assistant_db,
        draft=draft,
        requester_user_id=11,
        requester_role="teacher",
    )

    with pytest.raises(ValueError, match="目标"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=11,
            actor_role="teacher",
            payload=approval.payload_json,
            executor=lambda *_: {"ok": True},
        )


def test_action_ids_reject_fractional_values(db, teacher, student):
    owned = Class(name="owned", code="OWNED-ID", teacher_id=teacher.id)
    db.add(owned)
    assignment = Assignment(
        title="grading",
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
        ai_rule={"maxScore": 100},
    )
    db.add(assignment)
    db.commit()
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        class_id=owned.id,
        status="submitted",
    )
    db.add(submission)
    db.commit()

    with pytest.raises(ValueError, match="ID"):
        validate_action_permission(
            "create_assignment_draft",
            {"title": "draft", "classes": [owned.id + 0.5]},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )
    with pytest.raises(ValueError, match="格式"):
        validate_action_permission(
            "submit_teacher_score",
            {
                "submissionId": submission.id + 0.5,
                "assignmentId": assignment.id,
                "teacherScore": 80,
            },
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_create_ai_rule_rejects_orm_field_injection(db, teacher):
    with pytest.raises(ValueError, match="字段"):
        execute_approved_business_action(
            db,
            actor=teacher,
            action_type="create_ai_rule",
            payload={
                "name": "secure rule",
                "modelType": "deepseek",
                "prompt": "grade",
                "createdAt": "2000-01-01T00:00:00",
            },
            idempotency_key="rule-field-injection",
        )
