from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingReportPair,
    GradingRubric,
    RubricCriterion,
)
from app.agent.graphs.grading import (
    GRADING_AGENT_NODE,
    GRADING_DECISION_NODE,
    GRADING_REVIEW_NODE,
    GRADING_STRUCTURER_NODE,
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


def _pair() -> GradingReportPair:
    return GradingReportPair(
        primary=_draft(54, 36),
        review=_draft(52, 35),
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


# ========== 可选独立结构化节点（任务 5） ==========

def test_structurer_branch_routed_when_enabled():
    structurer_calls = []
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_report": "主批改普通报告"},
        lambda state: {"review_report": "独立复核普通报告"},
        structurer_node=lambda state: structurer_calls.append(1) or {
            "report_pair": _pair(),
            "usage": {"total_tokens": 10},
        },
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
        "structurer_enabled": True,
    })

    assert structurer_calls == [1]
    assert GRADING_STRUCTURER_NODE in result["visited_nodes"]
    assert GRADING_DECISION_NODE in result["visited_nodes"]
    assert result["outcome"].needs_human_review is False


def test_structurer_skipped_when_disabled():
    structurer_calls = []
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_draft": _draft(54, 36)},
        lambda state: {"review_draft": _draft(52, 35)},
        structurer_node=lambda state: structurer_calls.append(1) or {
            "report_pair": _pair(),
        },
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
        "structurer_enabled": False,
    })

    assert structurer_calls == []
    assert GRADING_STRUCTURER_NODE not in result["visited_nodes"]
    assert result["outcome"].needs_human_review is False


def test_structurer_failure_short_circuits_to_end():
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_report": "主批改普通报告"},
        lambda state: {"review_report": "独立复核普通报告"},
        structurer_node=lambda state: {"grading_failure": {
            "stage": GRADING_STRUCTURER_NODE,
            "error": "报告信息不足",
            "raw_response": "",
        }},
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
        "structurer_enabled": True,
    })

    assert "outcome" not in result
    assert result["grading_failure"]["stage"] == GRADING_STRUCTURER_NODE
    assert GRADING_STRUCTURER_NODE in result["visited_nodes"]
    assert GRADING_DECISION_NODE not in result["visited_nodes"]

