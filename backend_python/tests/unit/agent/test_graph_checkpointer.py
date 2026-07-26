from langgraph.checkpoint.memory import InMemorySaver

from app.agent.graphs.student import build_student_graph


class _Subagents:
    def learning_coach(self, state):
        return {}

    def feedback_explainer(self, state):
        return {}

    def learning_planner(self, state):
        return {}

    def final_reviewer(self, state):
        return {}


def test_graph_builder_accepts_official_langgraph_checkpointer():
    saver = InMemorySaver()
    graph = build_student_graph(_Subagents(), checkpointer=saver)

    assert graph.checkpointer is saver
