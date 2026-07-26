from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    RubricCriterion,
)
from tests.evals.cases.catalog import GRADING_CASES, PLAGIARISM_CASES


def test_all_grading_cases_produce_valid_structured_drafts():
    valid = 0
    for case in GRADING_CASES:
        rubric = GradingRubric(
            version=case["rubric_version"],
            criteria=[
                RubricCriterion(
                    criterion_id=f"c{i}",
                    title=f"维度 {i}",
                    max_score=max_score,
                )
                for i, max_score in enumerate(case["max_scores"])
            ],
        )
        draft = GradingDraft(
            rubric_version=case["rubric_version"],
            items=[
                CriterionGrade(
                    criterion_id=f"c{i}",
                    title=f"维度 {i}",
                    score=score,
                    max_score=case["max_scores"][i],
                    feedback="脱敏评语",
                )
                for i, score in enumerate(case["scores"])
            ],
            summary="脱敏汇总",
        )
        draft.validate_against(rubric)
        valid += draft.total_score == sum(case["scores"])
    assert valid / len(GRADING_CASES) >= 0.99


def test_plagiarism_eval_values_are_preserved_exactly():
    copied = [dict(case["deterministic_result"]) for case in PLAGIARISM_CASES]
    assert copied == [case["deterministic_result"] for case in PLAGIARISM_CASES]
