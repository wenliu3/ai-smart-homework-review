from app.agent.contracts import CriterionGrade, GradingDraft, GradingRubric, RubricCriterion
from app.agent.graphs.grading import (
    GRADING_AGENT_NODE,
    GRADING_REVIEW_NODE,
    NORMALIZE_CONTENT_NODE,
    build_grading_graph,
)


def _draft(score_a: float, score_b: float) -> GradingDraft:
    return GradingDraft(
        rubric_version="v1",
        items=[
            CriterionGrade(
                criterion_id="a",
                title="A",
                score=score_a,
                max_score=60,
                feedback="A feedback",
                evidence_refs=["submission:text:1"],
            ),
            CriterionGrade(
                criterion_id="b",
                title="B",
                score=score_b,
                max_score=40,
                feedback="B feedback",
                evidence_refs=["submission:text:1"],
            ),
        ],
        summary="summary",
    )


def _rubric() -> GradingRubric:
    return GradingRubric(
        version="v1",
        criteria=[
            RubricCriterion(criterion_id="a", title="A", max_score=60),
            RubricCriterion(criterion_id="b", title="B", max_score=40),
        ],
    )


def test_grading_graph_runs_named_independent_agents_in_order():
    calls = []

    def normalize(state):
        calls.append(NORMALIZE_CONTENT_NODE)
        return {"normalized_content": {"schema_version": "v1"}}

    def grade(state):
        calls.append(GRADING_AGENT_NODE)
        return {"grading_draft": _draft(54, 36)}

    def review(state):
        calls.append(GRADING_REVIEW_NODE)
        assert state["grading_draft"].total_score == 90
        return {"review_draft": _draft(52, 35)}

    result = build_grading_graph(normalize, grade, review).invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert calls == [
        NORMALIZE_CONTENT_NODE,
        GRADING_AGENT_NODE,
        GRADING_REVIEW_NODE,
    ]
    assert result["outcome"].needs_human_review is False
    assert result["visited_nodes"][:3] == calls


def test_grading_graph_requires_human_review_over_ten_percent_difference():
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_draft": _draft(60, 40)},
        lambda state: {"review_draft": _draft(45, 30)},
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert result["outcome"].score_difference == 25
    assert result["outcome"].needs_human_review is True
    assert "teacher_score" not in result
    assert "teacher_review_content" not in result

