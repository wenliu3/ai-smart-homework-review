"""学生/管理员图状态 schema 回归。

LangGraph 会静默丢弃 State TypedDict 之外的输入键与节点更新键：
编排层传入的 run_id / conversation_summary / recent_messages 必须能进入节点
（供 build_specialist_messages 构造多轮上下文），节点产出的
specialist_response 必须保留在最终状态（供 _build_artifacts 落库）。
"""
from app.agent.contracts import ReviewResult, SpecialistResponse
from app.agent.graphs.admin import build_admin_graph
from app.agent.graphs.student import build_student_graph


def test_student_graph_delivers_context_keys_and_keeps_specialist_response():
    seen = {}

    class Agents:
        def learning_coach(self, state):
            seen["run_id"] = state.get("run_id")
            seen["conversation_summary"] = state.get("conversation_summary")
            seen["recent_messages"] = state.get("recent_messages")
            response = SpecialistResponse(
                answer="先拆解题目条件",
                evidence_refs=["mysql://submissions/1?scope=current_student"],
            )
            return {
                "candidate_answer": response.answer,
                "evidence_refs": response.evidence_refs,
                "specialist_response": response,
            }

        def feedback_explainer(self, state):
            raise AssertionError("不应路由到反馈解释")

        def learning_planner(self, state):
            raise AssertionError("不应路由到学习规划")

        def final_reviewer(self, state):
            return {"review": ReviewResult(approved=True)}

    graph = build_student_graph(Agents())

    final_state = graph.invoke({
        "run_id": "run-schema-student",
        "actor": object(),
        "user_message": "这道题的思路是什么",
        "conversation_summary": "上次讨论了函数求导",
        "recent_messages": [{"role": "user", "content": "上次的问题"}],
        "visited_nodes": [],
    })

    assert seen == {
        "run_id": "run-schema-student",
        "conversation_summary": "上次讨论了函数求导",
        "recent_messages": [{"role": "user", "content": "上次的问题"}],
    }
    assert final_state["run_id"] == "run-schema-student"
    assert final_state["conversation_summary"] == "上次讨论了函数求导"
    assert final_state["recent_messages"] == [
        {"role": "user", "content": "上次的问题"},
    ]
    assert final_state["specialist_response"].answer == "先拆解题目条件"
    assert final_state["final_answer"] == "先拆解题目条件"


def test_admin_graph_delivers_context_keys_and_keeps_specialist_response():
    seen = {}

    class Agents:
        def operations_analysis(self, state):
            seen["run_id"] = state.get("run_id")
            seen["conversation_summary"] = state.get("conversation_summary")
            seen["recent_messages"] = state.get("recent_messages")
            response = SpecialistResponse(
                answer="平台整体运行平稳",
                evidence_refs=["mysql://platform/aggregate"],
            )
            return {
                "candidate_answer": response.answer,
                "evidence_refs": response.evidence_refs,
                "specialist_response": response,
            }

        def audit_analysis(self, state):
            raise AssertionError("不应路由到审计分析")

        def model_governance(self, state):
            raise AssertionError("不应路由到模型治理")

        def final_reviewer(self, state):
            return {"review": ReviewResult(approved=True)}

        def persist_approval(self, state):
            raise AssertionError("无 action_draft 时不应持久化审批")

    graph = build_admin_graph(Agents())

    final_state = graph.invoke({
        "run_id": "run-schema-admin",
        "actor": object(),
        "user_message": "汇总平台整体运行情况",
        "conversation_summary": "上次讨论了活跃度指标",
        "recent_messages": [{"role": "assistant", "content": "上次的分析结论"}],
        "visited_nodes": [],
    })

    assert seen == {
        "run_id": "run-schema-admin",
        "conversation_summary": "上次讨论了活跃度指标",
        "recent_messages": [{"role": "assistant", "content": "上次的分析结论"}],
    }
    assert final_state["run_id"] == "run-schema-admin"
    assert final_state["conversation_summary"] == "上次讨论了活跃度指标"
    assert final_state["recent_messages"] == [
        {"role": "assistant", "content": "上次的分析结论"},
    ]
    assert final_state["specialist_response"].answer == "平台整体运行平稳"
    assert final_state["final_answer"] == "平台整体运行平稳"
