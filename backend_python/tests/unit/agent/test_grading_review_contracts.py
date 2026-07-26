"""批改人工复核契约与预算扩展（规划阶段 3B.2 / 规格 §8.2、§15.2）。

- GradingDraft 新增 confidence / requires_human_review / review_reasons。
- GradingOutcome 聚合 review_reasons 供教师端展示。
- RunBudget 支持模型调用次数上限。
- 批改 Celery 任务带 120s 软超时。
"""
import pytest

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingOutcome,
)
from app.agent.runtime import BudgetExceeded, RunBudget


def _item(score=4.0):
    return CriterionGrade(
        criterion_id="overall",
        title="综合质量",
        score=score,
        max_score=5.0,
        feedback="内容完整",
        evidence_refs=["submission:text:1"],
    )


def _draft(**overrides):
    payload = {
        "rubric_version": "v1",
        "items": [_item()],
        "summary": "总体不错",
    }
    payload.update(overrides)
    return GradingDraft(**payload)


# ========== GradingDraft 扩展字段 ==========

def test_grading_draft_defaults_keep_backward_compatibility():
    draft = _draft()

    assert draft.confidence is None
    assert draft.requires_human_review is False
    assert draft.review_reasons == []


def test_grading_draft_accepts_self_reported_review_request():
    draft = _draft(
        confidence=0.35,
        requires_human_review=True,
        review_reasons=["提交内容与题目关联度低"],
    )

    assert draft.confidence == 0.35
    assert draft.requires_human_review is True
    assert draft.review_reasons == ["提交内容与题目关联度低"]


@pytest.mark.parametrize("confidence", [-0.1, 1.1, 2])
def test_grading_draft_confidence_must_be_a_ratio(confidence):
    with pytest.raises(ValueError):
        _draft(confidence=confidence)


def test_requesting_review_without_reason_is_rejected():
    with pytest.raises(ValueError, match="原因"):
        _draft(requires_human_review=True, review_reasons=[])


# ========== GradingOutcome 聚合 ==========

def test_grading_outcome_carries_review_reasons():
    outcome = GradingOutcome(
        primary=_draft(),
        review=_draft(score=2.0),
        score_difference=2.0,
        needs_human_review=True,
        review_reasons=["两次独立评分差异超过满分 10%"],
    )

    assert outcome.review_reasons == ["两次独立评分差异超过满分 10%"]


def test_grading_outcome_review_reasons_default_empty():
    outcome = GradingOutcome(
        primary=_draft(),
        review=_draft(),
        score_difference=0.0,
        needs_human_review=False,
    )

    assert outcome.review_reasons == []


# ========== RunBudget 模型调用上限 ==========

def test_run_budget_limits_model_calls():
    budget = RunBudget(max_model_calls=2)
    budget.consume_model_call()
    budget.consume_model_call()

    with pytest.raises(BudgetExceeded):
        budget.consume_model_call()


def test_grading_budget_matches_spec():
    from app.agent.runtime import grading_run_budget

    budget = grading_run_budget()

    assert budget.max_model_calls == 6
    assert budget.timeout_seconds == 120


# ========== Celery 软超时 ==========

def test_grading_task_has_soft_time_limit():
    from app.tasks.grading import run_grading_task

    assert run_grading_task.soft_time_limit == 120
