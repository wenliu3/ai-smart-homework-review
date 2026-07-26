import pytest

from app.agent.graphs.admin import build_admin_graph
from app.agent.graphs.student import build_student_graph
from app.agent.runtime import BudgetExceeded, RunBudget, RunCancelled


class _StudentAgents:
    def learning_coach(self, state):
        raise AssertionError("cancelled graph must not invoke the specialist")

    def feedback_explainer(self, state):
        raise AssertionError("cancelled graph must not invoke the specialist")

    def learning_planner(self, state):
        raise AssertionError("cancelled graph must not invoke the specialist")

    def final_reviewer(self, state):
        raise AssertionError("cancelled graph must not invoke the reviewer")


class _AdminAgents:
    def operations_analysis(self, state):
        raise AssertionError("cancelled graph must not invoke the specialist")

    def audit_analysis(self, state):
        raise AssertionError("cancelled graph must not invoke the specialist")

    def model_governance(self, state):
        raise AssertionError("cancelled graph must not invoke the specialist")

    def final_reviewer(self, state):
        raise AssertionError("cancelled graph must not invoke the reviewer")

    def persist_approval(self, state):
        raise AssertionError("cancelled graph must not persist an approval")


@pytest.mark.parametrize(
    ("builder", "agents"),
    [
        (build_student_graph, _StudentAgents()),
        (build_admin_graph, _AdminAgents()),
    ],
)
def test_role_graph_stops_at_next_node_boundary_after_cancellation(
    builder,
    agents,
):
    checks = iter((False, True))
    graph = builder(agents, is_cancelled=lambda: next(checks))

    with pytest.raises(RunCancelled):
        graph.invoke({
            "user_message": "default route",
            "visited_nodes": [],
        })


@pytest.mark.parametrize(
    ("builder", "agents"),
    [
        (build_student_graph, _StudentAgents()),
        (build_admin_graph, _AdminAgents()),
    ],
)
def test_role_graph_consumes_shared_node_budget(builder, agents):
    graph = builder(agents)

    with pytest.raises(BudgetExceeded):
        graph.invoke({
            "user_message": "default route",
            "visited_nodes": [],
            "runtime_budget": RunBudget(
                max_nodes=0,
                max_tool_calls=12,
                timeout_seconds=45,
            ),
        })
