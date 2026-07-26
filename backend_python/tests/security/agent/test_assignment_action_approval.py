"""作业类审批动作的安全边界（规划阶段 3A.2）。

覆盖四类风险：越权、载荷篡改、重复执行、归属/状态机错误。
"""
from datetime import datetime, timedelta

import pytest

from app.agent.tools.approval import create_action_draft
from app.crud import assignment as assignment_crud
from app.crud.action_execution import (
    execute_approved_business_action,
    validate_action_permission,
)
from app.crud.agent_approval import approve_and_execute, create_approval
from app.models import Assignment, Class

ASSIGNMENT_ACTIONS = (
    "publish_assignment",
    "update_assignment",
    "delete_assignment",
)


def _make_assignment(db, owner, *, status="draft", classes=None, title="第三章作业"):
    assignment = Assignment(
        title=title,
        teacher_id=owner.id,
        teacher_name=owner.name,
        classes=classes if classes is not None else [],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status=status,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def _payload(action, assignment_id, **extra):
    payload = {"assignmentId": assignment_id}
    payload.update(extra)
    return payload


# ========== 越权 ==========

@pytest.mark.parametrize("action", ASSIGNMENT_ACTIONS)
@pytest.mark.parametrize("role", ["student", "superadmin"])
def test_non_teacher_roles_cannot_approve_assignment_actions(action, role):
    with pytest.raises(ValueError, match="角色"):
        validate_action_permission(
            action,
            {"assignmentId": 1},
            actor_user_id=1,
            actor_role=role,
        )


@pytest.mark.parametrize("action", ASSIGNMENT_ACTIONS)
def test_teacher_cannot_touch_another_teachers_assignment(
    action, db, teacher, user_factory,
):
    other = user_factory("t_other_owner", "teacher")
    foreign = _make_assignment(db, other)

    with pytest.raises(ValueError, match="作业"):
        validate_action_permission(
            action,
            _payload(action, foreign.id, changes={"title": "改名"}),
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


@pytest.mark.parametrize("action", ASSIGNMENT_ACTIONS)
def test_missing_assignment_is_rejected_before_crud(action, db, teacher):
    with pytest.raises(ValueError, match="作业"):
        validate_action_permission(
            action,
            _payload(action, 999999, changes={"title": "改名"}),
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


@pytest.mark.parametrize("action", ASSIGNMENT_ACTIONS)
def test_soft_deleted_assignment_is_rejected(action, db, teacher):
    assignment = _make_assignment(db, teacher)
    assignment_crud.delete_assignment(db, assignment.id, teacher.id)

    with pytest.raises(ValueError, match="作业"):
        validate_action_permission(
            action,
            _payload(action, assignment.id, changes={"title": "改名"}),
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


@pytest.mark.parametrize("bad_id", [True, "1a", 0, -1, 1.5, None])
def test_malformed_assignment_id_is_rejected(bad_id, db, teacher):
    with pytest.raises(ValueError, match="格式"):
        validate_action_permission(
            "delete_assignment",
            {"assignmentId": bad_id},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


# ========== 发布状态机 ==========

def test_publish_requires_draft_status(db, teacher):
    klass = Class(name="c1", code="PUB1", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    classes = [{"id": str(klass.id), "name": klass.name}]

    published = _make_assignment(db, teacher, status="published", classes=classes)
    with pytest.raises(ValueError, match="状态"):
        validate_action_permission(
            "publish_assignment",
            {"assignmentId": published.id},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )

    terminated = _make_assignment(db, teacher, status="terminated", classes=classes)
    with pytest.raises(ValueError, match="状态"):
        validate_action_permission(
            "publish_assignment",
            {"assignmentId": terminated.id},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_publish_requires_at_least_one_class(db, teacher):
    assignment = _make_assignment(db, teacher, classes=[])

    with pytest.raises(ValueError, match="班级"):
        validate_action_permission(
            "publish_assignment",
            {"assignmentId": assignment.id},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


# ========== 更新字段白名单 ==========

@pytest.mark.parametrize("field", [
    "status", "teacherId", "teacher_id", "teacherName",
    "terminatedReason", "createdAt", "id", "deletedAt", "aiRule",
])
def test_update_rejects_unauthorized_change_fields(field, db, teacher):
    assignment = _make_assignment(db, teacher)

    with pytest.raises(ValueError, match="字段"):
        validate_action_permission(
            "update_assignment",
            {"assignmentId": assignment.id, "changes": {field: "x"}},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_update_rejects_unknown_top_level_keys(db, teacher):
    assignment = _make_assignment(db, teacher)

    with pytest.raises(ValueError, match="字段"):
        validate_action_permission(
            "update_assignment",
            {
                "assignmentId": assignment.id,
                "changes": {"title": "新标题"},
                "status": "published",
            },
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_update_rejects_empty_changes(db, teacher):
    assignment = _make_assignment(db, teacher)

    with pytest.raises(ValueError, match="变更"):
        validate_action_permission(
            "update_assignment",
            {"assignmentId": assignment.id, "changes": {}},
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_update_rejects_foreign_class_reassignment(db, teacher, user_factory):
    other = user_factory("t_class_owner", "teacher")
    foreign_class = Class(name="foreign", code="FGN1", teacher_id=other.id)
    db.add(foreign_class)
    db.commit()
    assignment = _make_assignment(db, teacher)

    with pytest.raises(ValueError, match="班级"):
        validate_action_permission(
            "update_assignment",
            {
                "assignmentId": assignment.id,
                "changes": {"classes": [foreign_class.id]},
            },
            actor_user_id=teacher.id,
            actor_role="teacher",
            db=db,
        )


def test_update_executor_forwards_only_whitelisted_change_keys(
    db, teacher, monkeypatch,
):
    """执行器只把 changes 白名单键透传给 crud；快照与 ID 绝不进入写路径。"""
    assignment = _make_assignment(db, teacher)
    captured = {}

    def fake_update(db_, assignment_id, teacher_id, data):
        captured["assignment_id"] = assignment_id
        captured["teacher_id"] = teacher_id
        captured["data"] = data
        return {"id": str(assignment_id)}

    monkeypatch.setattr(assignment_crud, "update_assignment", fake_update)

    execute_approved_business_action(
        db,
        actor=teacher,
        action_type="update_assignment",
        payload={
            "assignmentId": assignment.id,
            "changes": {"title": "新标题"},
            "beforeSnapshot": {"title": "第三章作业"},
        },
        idempotency_key="update-projection-1",
    )

    assert set(captured["data"]) == {"title"}
    assert captured["assignment_id"] == assignment.id
    assert captured["teacher_id"] == teacher.id


# ========== 篡改：草案目标与载荷绑定 ==========

def _assignment_draft(action, assignment_id, **extra):
    return create_action_draft(
        action_type=action,
        target_type="assignment",
        target_id=str(assignment_id),
        parameters=_payload(action, assignment_id, **extra),
        summary=f"{action} #{assignment_id}",
        risk_level="high",
        ttl_seconds=600,
    )


@pytest.mark.parametrize("action", ASSIGNMENT_ACTIONS)
def test_target_id_must_match_payload_assignment_id(action, assistant_db):
    draft = create_action_draft(
        action_type=action,
        target_type="assignment",
        target_id="42",
        parameters=_payload(action, 43, changes={"title": "x"}),
        summary="mismatch",
        risk_level="high",
        ttl_seconds=600,
    )
    approval = create_approval(
        assistant_db, draft=draft, requester_user_id=11, requester_role="teacher",
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


@pytest.mark.parametrize("action", ASSIGNMENT_ACTIONS)
def test_target_type_must_be_assignment(action, assistant_db):
    draft = create_action_draft(
        action_type=action,
        target_type="ai_rule",
        target_id="42",
        parameters=_payload(action, 42, changes={"title": "x"}),
        summary="wrong target type",
        risk_level="high",
        ttl_seconds=600,
    )
    approval = create_approval(
        assistant_db, draft=draft, requester_user_id=11, requester_role="teacher",
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


def test_tampered_snapshot_breaks_payload_hash(assistant_db):
    """快照存在草案 payload 里（决策 D2），任何改动都必须被逐字节复验拦下。"""
    draft = _assignment_draft(
        "delete_assignment", 7, beforeSnapshot={"title": "第三章作业"},
    )
    approval = create_approval(
        assistant_db, draft=draft, requester_user_id=11, requester_role="teacher",
    )
    tampered = dict(approval.payload_json)
    tampered["beforeSnapshot"] = {"title": "伪造的标题"}

    with pytest.raises(ValueError, match="载荷"):
        approve_and_execute(
            assistant_db,
            approval_id=approval.id,
            actor_user_id=11,
            actor_role="teacher",
            payload=tampered,
            executor=lambda *_: {"ok": True},
        )


# ========== 重复执行 ==========

def test_delete_action_soft_deletes_and_is_replay_safe(db, teacher):
    assignment = _make_assignment(db, teacher)

    first = execute_approved_business_action(
        db,
        actor=teacher,
        action_type="delete_assignment",
        payload={"assignmentId": assignment.id},
        idempotency_key="delete-replay-1",
    )
    second = execute_approved_business_action(
        db,
        actor=teacher,
        action_type="delete_assignment",
        payload={"assignmentId": assignment.id},
        idempotency_key="delete-replay-1",
    )

    assert first == second
    db.expire_all()
    row = db.query(Assignment).filter(Assignment.id == assignment.id).first()
    assert row.deleted_at is not None


def test_publish_action_transitions_status_once(db, teacher):
    klass = Class(name="c-pub", code="PUBX", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    assignment = _make_assignment(
        db, teacher, classes=[{"id": str(klass.id), "name": klass.name}],
    )

    first = execute_approved_business_action(
        db,
        actor=teacher,
        action_type="publish_assignment",
        payload={"assignmentId": assignment.id},
        idempotency_key="publish-replay-1",
    )
    second = execute_approved_business_action(
        db,
        actor=teacher,
        action_type="publish_assignment",
        payload={"assignmentId": assignment.id},
        idempotency_key="publish-replay-1",
    )

    assert first == second
    db.expire_all()
    assert db.query(Assignment).filter(
        Assignment.id == assignment.id,
    ).first().status == "published"
