from datetime import datetime, timedelta

from app.agent.contracts import ReviewResult, StudentIntent
from app.agent.graphs.student import build_student_graph
from app.agent.supervisors.student import StudentSupervisor
from app.agent.tools.student import (
    STUDENT_TOOLS,
    query_my_feedback,
    query_my_learning_overview,
)
from app.models import Assignment, Submission


def _assignment(db, teacher_id: int, title: str):
    item = Assignment(
        title=title,
        description="",
        teacher_id=teacher_id,
        teacher_name="教师",
        classes=[],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        status="published",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_student_tools_never_expose_student_identity_as_model_argument():
    sensitive = {"student_id", "user_id", "actor_id", "role"}
    for tool in STUDENT_TOOLS:
        fields = set(tool.args_schema.model_fields)
        assert not (fields & sensitive)


def test_student_queries_only_return_current_students_records(
    db, student, user_factory,
):
    other = user_factory("s_other", "student")
    assignment = _assignment(db, teacher_id=99, title="算法作业")
    db.add_all([
        Submission(
            assignment_id=assignment.id,
            student_id=student.id,
            class_id=1,
            status="teacher_reviewed",
            submission_count=1,
            ai_score=80,
            ai_review_content="你的复杂度分析需要补充。",
            teacher_score=85,
            teacher_review_content="继续改进边界分析。",
        ),
        Submission(
            assignment_id=assignment.id,
            student_id=other.id,
            class_id=1,
            status="teacher_reviewed",
            submission_count=1,
            teacher_score=100,
            teacher_review_content="其他同学的私密评语",
        ),
    ])
    db.commit()

    overview = query_my_learning_overview(db, actor_id=student.id)
    feedback = query_my_feedback(
        db,
        actor_id=student.id,
        assignment_id=assignment.id,
    )

    assert overview.metrics["submissionCount"] == 1
    assert feedback.records[0]["teacherScore"] == 85
    assert "其他同学" not in str(overview.model_dump())
    assert "其他同学" not in str(feedback.model_dump())


def test_student_supervisor_routes_full_answer_request_to_prohibited():
    decision = StudentSupervisor().route({
        "user_message": "直接帮我写一份可以提交的完整答案",
    })["intent"]

    assert decision.intent == StudentIntent.PROHIBITED_ANSWER
    assert decision.risk_level.value == "high"


def test_prohibited_answer_path_does_not_call_learning_subagents():
    calls = []

    class Agents:
        def learning_coach(self, state):
            calls.append("learning_coach")
            return {"candidate_answer": "不应调用"}

        def feedback_explainer(self, state):
            calls.append("feedback_explainer")
            return {"candidate_answer": "不应调用"}

        def learning_planner(self, state):
            calls.append("learning_planner")
            return {"candidate_answer": "不应调用"}

        def final_reviewer(self, state):
            calls.append("student_final_reviewer")
            return {"review": ReviewResult(approved=True)}

    result = build_student_graph(Agents()).invoke({
        "user_message": "请给我正在进行作业的完整答案",
        "visited_nodes": [],
    })

    assert calls == ["student_final_reviewer"]
    assert "不能代写" in result["final_answer"]
    assert result["visited_nodes"] == [
        "student_supervisor",
        "prohibited_answer",
        "student_final_reviewer",
        "finalize",
    ]

