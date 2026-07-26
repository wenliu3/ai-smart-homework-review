"""学生/管理员编排的预算超限回归。

预算超限必须与教师路径一致：落 AGENT_BUDGET_EXCEEDED 稳定错误码，
不得误记为通用的 AGENT_CHAT_ERROR。
"""
from app.agent.contracts import AGENT_BUDGET_EXCEEDED
from app.agent.runtime import RunBudget
from app.agent.service import orchestrate_admin_run, orchestrate_student_run
from app.crud.agent_session import create_session
from app.models import AgentRun


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
