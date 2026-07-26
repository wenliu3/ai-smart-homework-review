"""真流式与段落放行（规划阶段 5.4 / 决策 D5）。"""
import pytest

from app.agent.contracts import ReviewResult, SpecialistResponse
from app.agent.service import _emit_content_deltas, orchestrate_student_run
from app.crud.agent_session import create_session
from app.models import AgentStep


# ========== D5 段落放行 ==========

def _collect(final_answer):
    events = []
    _emit_content_deltas(lambda e: events.append(e), final_answer)
    return events


def test_paragraphs_are_released_one_by_one_and_reassemble():
    answer = "第一段结论。\n\n第二段依据。\n\n第三段建议。"

    events = _collect(answer)

    assert len(events) == 3
    assert "".join(e["data"]["content"] for e in events) == answer


def test_long_paragraph_falls_back_to_chunks():
    answer = "长" * 900

    events = _collect(answer)

    assert len(events) == 3  # 400 + 400 + 100
    assert "".join(e["data"]["content"] for e in events) == answer


def test_empty_answer_emits_nothing():
    assert _collect("") == []


# ========== 学生路径真流式 ==========

class _StreamingStudents:
    route_classifier = None
    topic_similarity_checker = None

    def learning_coach(self, state):
        response = SpecialistResponse(
            answer="先想想第一步。\n\n再检查你的推导。",
            evidence_refs=[],
        )
        return {
            "candidate_answer": response.answer,
            "evidence_refs": [],
            "specialist_response": response,
            "usage": {
                "prompt_tokens": 90, "completion_tokens": 20,
                "total_tokens": 110,
            },
        }

    def feedback_explainer(self, state):
        return {"candidate_answer": "x"}

    def learning_planner(self, state):
        return {"candidate_answer": "x"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


def test_student_run_streams_node_events_and_paragraph_deltas(assistant_db):
    session = create_session(
        assistant_db, user_id=8, actor_role="student", session_id="sessstream001",
    )
    emitted = []

    result = orchestrate_student_run(
        student_id=8,
        message="这道题怎么做，给点思路",
        session_id=session.id,
        request_id="req-stream-001",
        subagents=_StreamingStudents(),
        assistant_db=assistant_db,
        event_callback=emitted.append,
    )

    assert result.status == "completed"
    types = [e["type"] for e in emitted]
    # 节点级事件实时可见（不再是完成后合成）
    assert "route.selected" in types
    started = types.index("agent.started")
    completed = types.index("agent.completed")
    assert started < completed
    # 段落逐段放行：两段 → 两条 delta，全部先于 run.completed
    deltas = [e for e in emitted if e["type"] == "content.delta"]
    assert len(deltas) == 2
    assert types.index("content.delta") < types.index("run.completed")
    assert "".join(
        d["data"]["content"] for d in deltas
    ) == result.final_answer

    # Step 生命周期：specialist 有真实耗时且状态 completed
    assistant_db.expire_all()
    steps = {
        s.node_name: s
        for s in assistant_db.query(AgentStep).filter(
            AgentStep.run_id == result.run_id,
        )
    }
    assert steps["learning_coach_agent"].status == "completed"
    assert steps["learning_coach_agent"].duration_ms >= 1
    assert steps["learning_coach_agent"].usage_json["total_tokens"] == 110

    # 运行级 usage 聚合
    from app.models import AgentRun

    run = assistant_db.query(AgentRun).filter(
        AgentRun.id == result.run_id,
    ).one()
    assert run.usage_json["total_tokens"] == 110
