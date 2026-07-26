import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    RubricCriterion,
)


def test_rubric_requires_unique_criterion_ids_and_computes_total():
    rubric = GradingRubric(
        version="rubric-v2",
        criteria=[
            RubricCriterion(criterion_id="correctness", title="正确性", max_score=60),
            RubricCriterion(criterion_id="clarity", title="表达", max_score=40),
        ],
    )

    assert rubric.total_score == 100

    with pytest.raises(ValidationError):
        GradingRubric(
            version="bad",
            criteria=[
                RubricCriterion(criterion_id="same", title="A", max_score=50),
                RubricCriterion(criterion_id="same", title="B", max_score=50),
            ],
        )


def test_grading_draft_total_is_backend_computed_and_scores_are_bounded():
    draft = GradingDraft(
        rubric_version="rubric-v2",
        items=[
            CriterionGrade(
                criterion_id="correctness",
                title="正确性",
                score=54,
                max_score=60,
                feedback="主要结论正确",
                evidence_refs=["submission:text:1"],
            ),
            CriterionGrade(
                criterion_id="clarity",
                title="表达",
                score=36,
                max_score=40,
                feedback="结构清楚",
                evidence_refs=["submission:text:2"],
            ),
        ],
        summary="总体完成良好",
    )

    assert draft.total_score == 90
    assert draft.max_score == 100
    assert "total_score" not in GradingDraft.model_fields

    with pytest.raises(ValidationError):
        CriterionGrade(
            criterion_id="correctness",
            title="正确性",
            score=61,
            max_score=60,
            feedback="非法分数",
        )


def test_grading_draft_rejects_duplicate_or_missing_rubric_items():
    rubric = GradingRubric(
        version="v1",
        criteria=[
            RubricCriterion(criterion_id="a", title="A", max_score=50),
            RubricCriterion(criterion_id="b", title="B", max_score=50),
        ],
    )
    duplicate = GradingDraft(
        rubric_version="v1",
        items=[
            CriterionGrade(
                criterion_id="a", title="A", score=40, max_score=50, feedback="ok",
            ),
            CriterionGrade(
                criterion_id="a", title="A", score=45, max_score=50, feedback="ok",
            ),
        ],
        summary="duplicate",
    )

    with pytest.raises(ValueError, match="评分项"):
        duplicate.validate_against(rubric)

