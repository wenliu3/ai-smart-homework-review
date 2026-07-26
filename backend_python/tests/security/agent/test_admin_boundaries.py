from app.agent.contracts import AdminIntent, ReviewResult
from app.agent.graphs.admin import build_admin_graph
from app.agent.supervisors.admin import AdminSupervisor
from app.agent.tools.admin import (
    ADMIN_TOOLS,
    query_agent_runtime_metrics,
    query_model_governance_metrics,
    query_platform_operations,
)
from app.models import AgentMessage, AgentRun, AiModel


def test_admin_tools_do_not_expose_identity_or_secret_parameters():
    sensitive = {
        "admin_id",
        "user_id",
        "api_key",
        "access_key",
        "secret_key",
    }
    for tool in ADMIN_TOOLS:
        assert not (set(tool.args_schema.model_fields) & sensitive)


def test_admin_aggregates_exclude_chat_content_and_model_secrets(
    db, assistant_db, ai_model_factory, teacher, monkeypatch,
):
    model = ai_model_factory()
    model.access_key = "access-secret"
    model.secret_key = "secret-secret"
    db.commit()

    operations = query_platform_operations(db)
    governance = query_model_governance_metrics(db)
    runtime = query_agent_runtime_metrics(assistant_db)
    combined = str({
        "operations": operations.model_dump(),
        "governance": governance.model_dump(),
        "runtime": runtime.model_dump(),
    })

    assert operations.metrics["userCount"] >= 1
    assert "sk-test" not in combined
    assert "access-secret" not in combined
    assert "secret-secret" not in combined
    assert "baseUrl" not in combined
    assert "content" not in combined.lower()


def test_admin_supervisor_routes_configuration_change_as_high_risk():
    decision = AdminSupervisor().route({
        "user_message": "把默认模型切换为 deepseek",
    })["intent"]

    assert decision.intent == AdminIntent.MODEL_GOVERNANCE
    assert decision.risk_level.value == "high"
    assert decision.requires_approval is True


def test_admin_operations_graph_uses_named_agent_and_reviewer():
    calls = []

    class Agents:
        def operations_analysis(self, state):
            calls.append("operations_analysis_agent")
            return {
                "candidate_answer": "当前平台运行正常。",
                "evidence_refs": ["mysql://platform/aggregate"],
            }

        def audit_analysis(self, state):
            calls.append("audit_analysis_agent")
            return {"candidate_answer": "审计结果"}

        def model_governance(self, state):
            calls.append("model_governance_agent")
            return {"candidate_answer": "治理建议"}

        def final_reviewer(self, state):
            calls.append("admin_final_reviewer")
            return {"review": ReviewResult(approved=True)}

    result = build_admin_graph(Agents()).invoke({
        "user_message": "平台运营情况怎么样",
        "visited_nodes": [],
    })

    assert calls == ["operations_analysis_agent", "admin_final_reviewer"]
    assert result["final_answer"] == "当前平台运行正常。"
    assert result["visited_nodes"] == [
        "admin_supervisor",
        "operations_analysis_agent",
        "admin_final_reviewer",
        "finalize",
    ]

