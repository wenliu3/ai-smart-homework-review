"""管理员数据源与模型治理增强（规划阶段 5.3）。"""
from datetime import datetime, timedelta

import pytest

from app.agent.contracts import ModelProfile
from app.agent.gateway import ModelGateway
from app.agent.tools import admin as admin_tools
from app.models import Class, ClassStudent, OperationLog, Submission


# ========== OperationLog 聚合 ==========

def test_audit_metrics_aggregate_failures_and_denials(db):
    rows = [
        OperationLog(
            operator="t1", action="登录", module="认证", description="登录失败",
            endpoint="/api/auth/login", method="POST", status_code=401,
        ),
        OperationLog(
            operator="t1", action="登录", module="认证", description="登录失败",
            endpoint="/api/auth/login", method="POST", status_code=401,
        ),
        OperationLog(
            operator="t2", action="删除", module="作业管理", description="越权",
            endpoint="/api/assignments/9/delete", method="POST", status_code=403,
        ),
        OperationLog(
            operator="t2", action="创建", module="班级管理", description="正常",
            endpoint="/api/classes", method="POST", status_code=200,
        ),
    ]
    db.add_all(rows)
    db.commit()

    result = admin_tools.query_audit_metrics(db)

    assert result.status == "ok"
    assert result.metrics["loginFailureCount"] == 2
    assert result.metrics["permissionDeniedCount"] == 1
    assert result.metrics["operationCount"] == 4
    top = {item["endpoint"]: item["count"] for item in result.records}
    assert top["/api/auth/login"] == 2
    assert result.evidence_refs
    # 审计盲区必须如实声明（GET 与部分路径不入日志）
    assert result.limitations


def test_audit_metrics_never_leak_descriptions(db):
    db.add(OperationLog(
        operator="t1", action="更新", module="用户管理",
        description="把学生张三的密码重置为 123456",
        endpoint="/api/users/3", method="PUT", status_code=200,
    ))
    db.commit()

    result = admin_tools.query_audit_metrics(db)

    assert "张三" not in str(result.model_dump())
    assert "123456" not in str(result.model_dump())


# ========== 活跃度与班级规模 ==========

def test_activity_metrics_cover_classes_and_submissions(db, teacher, student):
    klass = Class(name="活跃班", code="ACT1", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    db.add(ClassStudent(
        class_id=klass.id, student_id=student.id, status="active",
    ))
    db.add(Submission(
        assignment_id=1, student_id=student.id, class_id=klass.id,
        status="submitted", submitted_at=datetime.now(),
    ))
    db.commit()

    result = admin_tools.query_activity_metrics(db)

    assert result.status == "ok"
    assert result.metrics["activeClassCount"] == 1
    assert result.metrics["avgClassSize"] == 1.0
    assert result.metrics["recentSubmissionCount"] >= 1
    assert result.evidence_refs


# ========== 模型连通性探测 ==========

def test_connectivity_probe_masks_secrets(db, ai_model_factory, monkeypatch):
    model = ai_model_factory(api_key="sk-super-secret-key-123456")

    from app.crud import ai_model as ai_model_crud

    monkeypatch.setattr(
        ai_model_crud,
        "test_connection",
        lambda db_, code: {"success": True, "responseTime": 88, "message": "连接正常"},
    )

    result = admin_tools.query_model_connectivity(db)

    assert result.status == "ok"
    assert result.records[0]["code"] == model.code
    assert result.records[0]["reachable"] is True
    serialized = str(result.model_dump())
    assert "sk-super-secret-key-123456" not in serialized


def test_new_admin_tools_are_registered_for_llm():
    names = {tool.name for tool in admin_tools.ADMIN_TOOLS}

    assert {"get_audit_metrics", "get_activity_metrics",
            "get_model_connectivity"} <= names


# ========== 能力标签与档位绑定 ==========

def test_vision_profile_prefers_capability_tagged_model(db, ai_model_factory):
    ai_model_factory(code="text-model", is_default=True)
    vision = ai_model_factory(code="vision-model", is_default=False)
    vision.capabilities = ["text", "vision"]
    db.commit()

    gw = ModelGateway()

    assert gw.get_config_for_profile(
        db, ModelProfile.VISION_GRADER,
    ).code == "vision-model"
    # 其他档位仍走默认链
    assert gw.get_config_for_profile(
        db, ModelProfile.GENERAL,
    ).code == "text-model"


def test_profile_binding_beats_capability_tag(db, ai_model_factory):
    ai_model_factory(code="default-model", is_default=True)
    tagged = ai_model_factory(code="tagged-model", is_default=False)
    tagged.capabilities = ["vision"]
    bound = ai_model_factory(code="bound-model", is_default=False)
    bound.profile_bindings = {"vision_grader": True}
    db.commit()

    gw = ModelGateway()

    assert gw.get_config_for_profile(
        db, ModelProfile.VISION_GRADER,
    ).code == "bound-model"


def test_vision_profile_falls_back_to_default_chain(db, ai_model_factory):
    ai_model_factory(code="only-default", is_default=True)

    gw = ModelGateway()

    assert gw.get_config_for_profile(
        db, ModelProfile.VISION_GRADER,
    ).code == "only-default"


def test_migration_adds_ai_model_capability_columns(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, inspect

    from tests.unit.test_alembic_migrations import _make_config

    db_path = tmp_path / "capabilities.db"
    command.upgrade(_make_config(db_path), "head")

    insp = inspect(create_engine(f"sqlite:///{db_path.as_posix()}"))
    columns = {col["name"] for col in insp.get_columns("ai_models")}
    assert {"capabilities", "profile_bindings"} <= columns


# ========== 受控正文访问（规格 §14.2） ==========

@pytest.fixture()
def finished_run(assistant_db, student):
    from app.crud import agent_run
    from app.crud.agent_session import create_session

    session = create_session(
        assistant_db, user_id=student.id, actor_role="student",
    )
    run = agent_run.create_run(
        assistant_db, session_id=session.id, user_id=student.id, intent="pending",
    )
    agent_run.finalize_run(
        assistant_db, run.id, student.id,
        final_output="这是运行的最终正文内容。",
    )
    return run


def test_teacher_cannot_access_run_content(
    client, teacher, auth_header, finished_run,
):
    response = client.post(
        f"/api/assistant/admin/runs/{finished_run.id}/content-access",
        headers=auth_header(teacher),
        json={"reason": "排查用户投诉"},
    )

    assert response.status_code == 403


def test_admin_content_access_requires_reason(
    client, user_factory, auth_header, finished_run,
):
    admin = user_factory("sa_content_1", "superadmin")

    response = client.post(
        f"/api/assistant/admin/runs/{finished_run.id}/content-access",
        headers=auth_header(admin),
        json={"reason": "  "},
    )

    assert response.status_code == 400


def test_admin_content_access_returns_content_and_writes_audit_log(
    client, db, user_factory, auth_header, finished_run,
):
    admin = user_factory("sa_content_2", "superadmin")

    response = client.post(
        f"/api/assistant/admin/runs/{finished_run.id}/content-access",
        headers=auth_header(admin),
        json={"reason": "排查用户投诉 #1024"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["finalOutput"] == "这是运行的最终正文内容。"

    log = db.query(OperationLog).filter(
        OperationLog.module == "运行审计",
    ).one()
    assert finished_run.id in log.description
    assert "排查用户投诉" in log.description
    # 审计日志绝不落正文
    assert "最终正文" not in log.description
    assert log.operator == admin.username
