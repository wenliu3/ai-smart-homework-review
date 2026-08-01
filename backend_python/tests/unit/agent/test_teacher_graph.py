"""教师主管 LangGraph 的多 Agent 路由测试。"""
from app.agent.orchestration.graph import build_teacher_graph


class FakeSpecialists:
    def teaching_data(self, state):
        return {"candidate_answer": "数据回答"}

    def teaching_strategy(self, state):
        return {"candidate_answer": "策略回答"}

    def final_reviewer(self, state):
        return {"review": {"approved": True, "issues": []}}


def test_data_route_runs_data_agent_then_reviewer():
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    assert result["visited_nodes"] == ["route", "teaching_data", "final_reviewer", "finalize"]
    assert result["final_answer"] == "数据回答"


def test_strategy_route_runs_strategy_agent_then_reviewer():
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "分析最近成绩并给教学建议", "visited_nodes": []})

    assert result["visited_nodes"] == ["route", "teaching_strategy", "final_reviewer", "finalize"]
    assert result["final_answer"] == "策略回答"


def test_write_request_never_runs_specialist():
    graph = build_teacher_graph(FakeSpecialists())
    result = graph.invoke({"user_message": "帮我发布一份作业", "visited_nodes": []})

    assert result["visited_nodes"] == ["route", "finalize"]
    assert "只读" in result["final_answer"]
