"""SSE worker 异常脱敏与 finalize 取消竞态回归。

- pydantic ValidationError 是 ValueError 子类：字段名/输入值绝不能透传给客户端。
- 只有会话归属类已知安全消息可以原样透传。
- 「最后节点完成后、finalize 前取消运行」的竞态必须转为 run.cancelled，
  而不是携带内部 CRUD 消息的 run.failed。
"""
import json

import pytest
from pydantic import ValidationError

from app.agent import service
from app.agent.contracts import (
    AGENT_RUN_CANCELLED,
    ActorContext,
    ReviewResult,
    SAFE_CHAT_ERROR_MESSAGE,
)
from app.crud import agent_run as agent_run_crud
from app.crud.agent_session import create_session


def _make_validation_error() -> ValidationError:
    try:
        ActorContext.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("应产生 ValidationError")


def _collect_payloads(stream) -> list[dict]:
    return [
        json.loads(event.data)
        for event in stream
        if event.event is None
    ]


def _run_teacher_stream():
    return service.stream_assistant_events(
        teacher_id=1,
        message="hi",
        session_id="session-1",
        request_id="request-1",
    )


def _run_role_stream(orchestrate):
    return service._stream_role_events(
        actor_id=1,
        request_id="request-1",
        orchestrate=orchestrate,
        orchestrate_kwargs={},
        container_factory=lambda db: object(),
    )


@pytest.mark.parametrize("stream_kind", ["teacher", "role"])
def test_stream_worker_sanitizes_validation_error_details(
    monkeypatch, stream_kind,
):
    error = _make_validation_error()

    def raise_validation_error(**_kwargs):
        raise error

    if stream_kind == "teacher":
        monkeypatch.setattr(
            service, "orchestrate_teacher_run", raise_validation_error,
        )
        payloads = _collect_payloads(_run_teacher_stream())
    else:
        payloads = _collect_payloads(_run_role_stream(raise_validation_error))

    failed = [p for p in payloads if p["type"] == "run.failed"]
    assert len(failed) == 1
    assert failed[0]["data"]["message"] == SAFE_CHAT_ERROR_MESSAGE
    # 校验异常的字段名与输入细节不得出现在任何事件里
    dumped = json.dumps(payloads, ensure_ascii=False)
    assert "user_id" not in dumped
    assert "validation error" not in dumped


@pytest.mark.parametrize(
    ("stream_kind", "safe_message"),
    [
        ("teacher", "会话不存在或不属于当前用户"),
        ("role", "学生会话不存在或不属于当前用户"),
        ("role", "管理员会话不存在或不属于当前用户"),
    ],
)
def test_stream_worker_passes_through_known_ownership_messages(
    monkeypatch, stream_kind, safe_message,
):
    def raise_ownership_error(**_kwargs):
        raise ValueError(safe_message)

    if stream_kind == "teacher":
        monkeypatch.setattr(
            service, "orchestrate_teacher_run", raise_ownership_error,
        )
        payloads = _collect_payloads(_run_teacher_stream())
    else:
        payloads = _collect_payloads(_run_role_stream(raise_ownership_error))

    failed = [p for p in payloads if p["type"] == "run.failed"]
    assert len(failed) == 1
    assert failed[0]["data"]["message"] == safe_message


class _TeacherSpecialists:
    def teaching_data(self, state):
        raise AssertionError("寒暄消息不应进入数据 Agent")

    def teaching_strategy(self, state):
        raise AssertionError("寒暄消息不应进入策略 Agent")

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True)}


class _StudentSubagents:
    def learning_coach(self, state):
        raise AssertionError("寒暄消息不应进入学习辅导 Agent")

    def feedback_explainer(self, state):
        raise AssertionError("寒暄消息不应进入反馈解释 Agent")

    def learning_planner(self, state):
        raise AssertionError("寒暄消息不应进入学习规划 Agent")

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True)}


def _patch_cancel_before_finalize(monkeypatch):
    """模拟竞态：最后节点完成后、finalize 提交前用户取消了运行。"""
    original = agent_run_crud.finalize_run

    def cancel_then_finalize(db, **kwargs):
        agent_run_crud.cancel_run(
            db, kwargs["run_id"], user_id=kwargs["user_id"],
        )
        return original(db, **kwargs)

    monkeypatch.setattr(agent_run_crud, "finalize_run", cancel_then_finalize)


def test_teacher_finalize_cancel_race_reports_run_cancelled(
    assistant_db, monkeypatch,
):
    session = create_session(
        assistant_db, user_id=11, actor_role="teacher", title="教师会话",
    )
    _patch_cancel_before_finalize(monkeypatch)

    result = service.orchestrate_teacher_run(
        teacher_id=11,
        message="你好",
        session_id=session.id,
        request_id="req-race-teacher",
        specialists=_TeacherSpecialists(),
        assistant_db=assistant_db,
    )

    assert result.status == "cancelled"
    assert result.error_code == AGENT_RUN_CANCELLED
    assert result.events[-1]["type"] == "run.cancelled"
    assert all(event["type"] != "run.failed" for event in result.events)


def test_student_finalize_cancel_race_reports_run_cancelled(
    assistant_db, monkeypatch,
):
    session = create_session(
        assistant_db, user_id=12, actor_role="student", title="学生会话",
    )
    _patch_cancel_before_finalize(monkeypatch)

    result = service.orchestrate_student_run(
        student_id=12,
        message="你好",
        session_id=session.id,
        request_id="req-race-student",
        subagents=_StudentSubagents(),
        assistant_db=assistant_db,
    )

    assert result.status == "cancelled"
    assert result.error_code == AGENT_RUN_CANCELLED
    assert result.events[-1]["type"] == "run.cancelled"
    assert all(event["type"] != "run.failed" for event in result.events)
