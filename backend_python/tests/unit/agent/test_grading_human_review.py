"""批改失败降级与转人工规则（规划阶段 3B.2）。

不变式：结构化校验失败或证据缺失时，结果**转人工**而不是被丢弃；
图失败分支不产出 outcome，由任务层落原始草案 Artifact 并提示教师。
"""
import pytest

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    RubricCriterion,
)
from app.agent.graphs.grading import (
    GRADING_AGENT_NODE,
    GRADING_DECISION_NODE,
    GRADING_REVIEW_NODE,
    build_grading_graph,
)


def _rubric() -> GradingRubric:
    return GradingRubric(
        version="v1",
        criteria=[RubricCriterion(
            criterion_id="overall", title="综合质量", max_score=100,
        )],
    )


def _draft(score=80.0, evidence=("submission:text:1",), **overrides):
    payload = {
        "rubric_version": "v1",
        "items": [CriterionGrade(
            criterion_id="overall",
            title="综合质量",
            score=score,
            max_score=100,
            feedback="内容完整",
            evidence_refs=list(evidence),
        )],
        "summary": "总体不错",
    }
    payload.update(overrides)
    return GradingDraft(**payload)


def _invoke(grade_update, review_update):
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: grade_update,
        lambda state: review_update,
    )
    return graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })


# ========== decide 转人工规则 ==========

def test_score_difference_reason_is_recorded():
    result = _invoke(
        {"grading_draft": _draft(score=90)},
        {"review_draft": _draft(score=60)},
    )

    outcome = result["outcome"]
    assert outcome.needs_human_review is True
    assert any("差异" in reason for reason in outcome.review_reasons)


def test_missing_evidence_forces_human_review():
    result = _invoke(
        {"grading_draft": _draft(evidence=())},
        {"review_draft": _draft()},
    )

    outcome = result["outcome"]
    assert outcome.needs_human_review is True
    assert any("证据" in reason for reason in outcome.review_reasons)


def test_model_self_reported_review_request_is_honored():
    flagged = _draft(
        confidence=0.2,
        requires_human_review=True,
        review_reasons=["提交内容与题目关联度低"],
    )
    result = _invoke(
        {"grading_draft": flagged},
        {"review_draft": _draft()},
    )

    outcome = result["outcome"]
    assert outcome.needs_human_review is True
    assert "提交内容与题目关联度低" in outcome.review_reasons


def test_clean_outcome_has_no_reasons():
    result = _invoke(
        {"grading_draft": _draft(score=80)},
        {"review_draft": _draft(score=78)},
    )

    outcome = result["outcome"]
    assert outcome.needs_human_review is False
    assert outcome.review_reasons == []


# ========== 结构化失败分支：跳过后续节点、不产出 outcome ==========

def test_grading_failure_skips_review_and_decision():
    review_calls = []
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_failure": {
            "stage": GRADING_AGENT_NODE,
            "error": "评分项必须与量表完整且唯一对应",
            "raw_response": "{'items': 'broken'}",
        }},
        lambda state: review_calls.append(1) or {"review_draft": _draft()},
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert review_calls == []
    assert "outcome" not in result
    assert result["grading_failure"]["stage"] == GRADING_AGENT_NODE
    assert GRADING_DECISION_NODE not in result["visited_nodes"]


def test_review_failure_skips_decision():
    graph = build_grading_graph(
        lambda state: {"normalized_content": {"schema_version": "v1"}},
        lambda state: {"grading_draft": _draft()},
        lambda state: {"grading_failure": {
            "stage": GRADING_REVIEW_NODE,
            "error": "结构化输出缺失",
            "raw_response": "",
        }},
    )

    result = graph.invoke({
        "rubric": _rubric(),
        "submission_id": 7,
        "submission_count": 2,
    })

    assert "outcome" not in result
    assert result["grading_failure"]["stage"] == GRADING_REVIEW_NODE
