"""平台开关与灰度（规划阶段 5.6）。

- MULTI_AGENT_ENABLED=False 时新版助手入口整体关闭。
- 教师白名单灰度：名单非空时只放行名单内教师；学生/管理员不受教师名单影响。
- page_context 请求字段进入图状态，供 specialist prompt 消费。
"""
import pytest

from app.config import settings


@pytest.fixture()
def _restore_flags():
    enabled = settings.MULTI_AGENT_ENABLED
    whitelist = settings.MULTI_AGENT_TEACHER_WHITELIST
    yield
    settings.MULTI_AGENT_ENABLED = enabled
    settings.MULTI_AGENT_TEACHER_WHITELIST = whitelist


def _stream(client, headers, session_id="sessflag00000001"):
    return client.post(
        "/api/assistant/runs/stream",
        headers=headers,
        json={"message": "你好", "session_id": session_id},
    )


def test_flag_defaults_keep_assistant_enabled():
    assert settings.MULTI_AGENT_ENABLED is True
    assert settings.MULTI_AGENT_TEACHER_WHITELIST == ""


def test_disabled_platform_rejects_stream(
    client, teacher, auth_header, _restore_flags,
):
    settings.MULTI_AGENT_ENABLED = False

    response = _stream(client, auth_header(teacher))

    assert response.status_code == 400
    assert "助手" in response.json()["message"]


def test_teacher_outside_whitelist_is_rejected(
    client, teacher, auth_header, _restore_flags,
):
    settings.MULTI_AGENT_TEACHER_WHITELIST = "999999"

    response = _stream(client, auth_header(teacher))

    assert response.status_code == 400


def test_whitelisted_teacher_passes_gate(
    client, assistant_db, teacher, auth_header, _restore_flags,
):
    from app.crud.agent_session import create_session

    settings.MULTI_AGENT_TEACHER_WHITELIST = f"{teacher.id},424242"
    session = create_session(
        assistant_db, user_id=teacher.id, actor_role="teacher",
    )

    response = _stream(client, auth_header(teacher), session_id=session.id)

    # 通过灰度闸门即进入 SSE 流（不会 400；流内容依赖模型配置，不在此断言）
    assert response.status_code == 200


def test_student_is_not_affected_by_teacher_whitelist(
    client, assistant_db, student, auth_header, _restore_flags,
):
    from app.crud.agent_session import create_session

    settings.MULTI_AGENT_TEACHER_WHITELIST = "999999"
    session = create_session(
        assistant_db, user_id=student.id, actor_role="student",
    )

    response = _stream(client, auth_header(student), session_id=session.id)

    assert response.status_code == 200


# ========== page_context 接线 ==========

def test_page_context_reaches_specialist_messages(assistant_db):
    from app.agent.service import orchestrate_teacher_run
    from app.agent.subagents.messages import build_specialist_messages
    from app.crud.agent_session import create_session
    from tests.integration.agent.test_run_usage_persistence import (
        _UsageSpecialists,
    )

    captured = {}

    class _ContextSpecialists(_UsageSpecialists):
        def teaching_data(self, state):
            captured["page_context"] = state.get("page_context")
            captured["messages"] = build_specialist_messages(state)
            return super().teaching_data(state)

    session = create_session(
        assistant_db, user_id=7, actor_role="teacher", session_id="sessctx000001",
    )

    orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-ctx-001",
        specialists=_ContextSpecialists(),
        assistant_db=assistant_db,
        page_context="teacher/correcting",
    )

    assert captured["page_context"] == "teacher/correcting"
    serialized = "".join(str(m.content) for m in captured["messages"])
    assert "teacher/correcting" in serialized
