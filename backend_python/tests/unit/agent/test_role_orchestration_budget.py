"""学生/管理员编排的预算超限回归。

预算超限必须与教师路径一致：落 AGENT_BUDGET_EXCEEDED 稳定错误码，
不得误记为通用的 AGENT_CHAT_ERROR。
"""
from unittest.mock import patch

import app.agent.service as service_module
from app.agent.contracts import AGENT_BUDGET_EXCEEDED
from app.agent.runtime import RunBudget
from app.agent.service import (
    orchestrate_admin_run,
    orchestrate_student_run,
    orchestrate_teacher_run,
)
from app.crud.agent_session import create_session
from app.models import AgentRun


class _TeacherAgents:
    def route_classifier(self, message):
        raise AssertionError("预算超限时不应调用分类器")

    def teaching_data(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def teaching_strategy(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def action_draft(self, state):
        raise AssertionError("预算超限时不应调用写操作 Agent")

    def final_reviewer(self, state):
        raise AssertionError("预算超限时不应调用审核 Agent")

    def persist_approval(self, state):
        raise AssertionError("预算超限时不应持久化审批")


class _StudentAgents:
    def learning_coach(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def feedback_explainer(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def learning_planner(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def final_reviewer(self, state):
        raise AssertionError("预算超限时不应调用审核 Agent")


class _AdminAgents:
    def operations_analysis(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def audit_analysis(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def model_governance(self, state):
        raise AssertionError("预算超限时不应调用专业 Agent")

    def final_reviewer(self, state):
        raise AssertionError("预算超限时不应调用审核 Agent")

    def persist_approval(self, state):
        raise AssertionError("预算超限时不应持久化审批")


def _zero_node_budget() -> RunBudget:
    return RunBudget(max_nodes=0, max_tool_calls=12, timeout_seconds=45)


def test_student_orchestration_reports_stable_budget_exceeded_code(assistant_db):
    session = create_session(
        assistant_db, user_id=71, actor_role="student", title="学生会话",
    )

    result = orchestrate_student_run(
        student_id=71,
        message="你好",
        session_id=session.id,
        request_id="req-budget-student",
        subagents=_StudentAgents(),
        assistant_db=assistant_db,
        budget=_zero_node_budget(),
    )

    assert result.status == "failed"
    assert result.error_code == AGENT_BUDGET_EXCEEDED
    assert result.events[-1] == {
        "type": "run.failed",
        "data": {"run_id": result.run_id, "error_code": AGENT_BUDGET_EXCEEDED},
    }
    saved = assistant_db.query(AgentRun).filter(
        AgentRun.id == result.run_id,
    ).one()
    assert saved.status == "failed"
    assert saved.error_code == AGENT_BUDGET_EXCEEDED


def test_admin_orchestration_reports_stable_budget_exceeded_code(assistant_db):
    session = create_session(
        assistant_db, user_id=81, actor_role="superadmin", title="管理员会话",
    )

    result = orchestrate_admin_run(
        admin_id=81,
        message="你好",
        session_id=session.id,
        request_id="req-budget-admin",
        subagents=_AdminAgents(),
        assistant_db=assistant_db,
        budget=_zero_node_budget(),
    )

    assert result.status == "failed"
    assert result.error_code == AGENT_BUDGET_EXCEEDED
    assert result.events[-1] == {
        "type": "run.failed",
        "data": {"run_id": result.run_id, "error_code": AGENT_BUDGET_EXCEEDED},
    }
    saved = assistant_db.query(AgentRun).filter(
        AgentRun.id == result.run_id,
    ).one()
    assert saved.status == "failed"
    assert saved.error_code == AGENT_BUDGET_EXCEEDED


def test_teacher_budget_log_has_reason_and_counts_but_sse_stays_stable(
    assistant_db,
):
    """预算超限日志带 reason 与计数；SSE 事件只暴露稳定错误码，不泄露内部细节。"""
    session = create_session(
        assistant_db, user_id=7, actor_role="teacher", title="教师会话",
    )

    # 直接替身 logger.warning：完整测试套件里可能有他处全局关闭 logging，
    # 因此不依赖 handler/caplog，只断言被调用的日志格式与计数参数。
    with patch.object(
        service_module.logger, "warning",
    ) as mock_warning:
        result = orchestrate_teacher_run(
            teacher_id=7,
            message="你帮我起个作业草稿",
            session_id=session.id,
            request_id="req-budget-log",
            specialists=_TeacherAgents(),
            assistant_db=assistant_db,
            budget=_zero_node_budget(),
        )

    assert result.status == "failed"
    assert result.error_code == AGENT_BUDGET_EXCEEDED

    matched = [
        call for call in mock_warning.call_args_list
        if (call.args and "Teacher run budget exceeded" in str(call.args[0]))
    ]
    assert matched, "应记录 Teacher run budget exceeded 日志"
    fmt = matched[0].args[0]
    # 调用签名：logger.warning(fmt, run_id, e.code, str(e), 计数...)
    assert "reason=%s" in fmt
    assert "节点数" in str(matched[0].args[3])  # str(e)：真正的超限原因
    assert "nodes=%s/%s" in fmt
    assert "tools=%s/%s" in fmt and "models=%s/%s" in fmt and "remaining=%.2fs" in fmt

    # SSE 事件只带稳定错误码，不得把 reason/内部计数暴露给前端
    failed = [e for e in result.events if e["type"] == "run.failed"]
    assert failed
    assert failed[-1]["data"].keys() == {"run_id", "error_code"}
    assert failed[-1]["data"]["error_code"] == AGENT_BUDGET_EXCEEDED
    assert all(
        "reason" not in str(e) and "节点数" not in str(e)
        for e in result.events
    )
