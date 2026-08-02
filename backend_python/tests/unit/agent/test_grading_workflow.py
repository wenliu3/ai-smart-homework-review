"""单 Agent 批改图测试：规范化 → 主批改 → 确定性决策。"""
from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    RubricCriterion,
)
from app.agent.graphs.grading import (
    GRADING_AGENT_NODE,
    GRADING_DECISION_NODE,
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


def test_grading_graph_runs_nodes_in_order():
    calls = []

    def normalize(state):
        calls.append(NORMALIZE_CONTENT_NODE)
        return {"normalized_content": {"schema_version": "v1"}}

    def grade(state):
        calls.append(GRADING_AGENT_NODE)
        return {"grading_draft": _draft(54, 36)}

    result = build_grading_graph(normalize, grade).invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert calls == [NORMALIZE_CONTENT_NODE, GRADING_AGENT_NODE]
    assert result["outcome"].needs_human_review is False
    assert result["visited_nodes"] == [
        NORMALIZE_CONTENT_NODE,
        GRADING_AGENT_NODE,
        GRADING_DECISION_NODE,
    ]


def test_grading_graph_requires_human_review_when_evidence_missing():
    # 主批改草案缺证据：确定性转人工检查触发，不写入分数
    draft = _draft(60, 40)
    draft.items[0].evidence_refs = []

    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_draft": draft},
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert result["outcome"].needs_human_review is True
    assert "主批改评分缺少提交证据" in result["outcome"].review_reasons[0]


def test_grading_graph_short_circuits_on_failure():
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_failure": {
            "stage": GRADING_AGENT_NODE,
            "error": "结构化校验失败",
            "raw_response": "",
        }},
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert "outcome" not in result
    assert result["grading_failure"]["stage"] == GRADING_AGENT_NODE
    assert GRADING_DECISION_NODE not in result["visited_nodes"]
