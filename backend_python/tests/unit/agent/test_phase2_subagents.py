from types import SimpleNamespace

from app.agent.contracts import (
    CriterionGrade,
    GradingDraft,
    GradingRubric,
    NormalizedSubmissionContent,
    RubricCriterion,
)
from app.agent.subagents.grading import create_node as create_grading_node
from app.agent.subagents.grading_review import create_node as create_review_node
from app.agent.subagents.plagiarism_analysis import (
    create_node as create_plagiarism_node,
)


class _FakeAgent:
    def __init__(self, structured_response):
        self.structured_response = structured_response
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        return {"structured_response": self.structured_response}


class _Registry:
    def __init__(self, agents):
        self.agents = agents

    def get_specialist(self, name, db):
        return self.agents[name]


def _rubric():
    return GradingRubric(
        version="v1",
        criteria=[RubricCriterion(
            criterion_id="quality", title="质量", max_score=100,
        )],
    )


def _draft():
    return GradingDraft(
        rubric_version="v1",
        items=[CriterionGrade(
            criterion_id="quality",
            title="质量",
            score=85,
            max_score=100,
            feedback="完成良好",
            evidence_refs=["submission:text:1"],
        )],
        summary="总体完成良好",
    )


def test_grading_and_review_nodes_use_distinct_agents_and_validate_rubric():
    grader = _FakeAgent(_draft().model_dump())
    reviewer = _FakeAgent(_draft().model_dump())
    registry = _Registry({"grading": grader, "grading_review": reviewer})
    state = {
        "rubric": _rubric(),
        "normalized_content": NormalizedSubmissionContent(),
    }

    grade_update = create_grading_node(object(), registry)(state)
    review_update = create_review_node(object(), registry)({
        **state,
        **grade_update,
    })

    assert grade_update["grading_draft"].total_score == 85
    assert review_update["review_draft"].total_score == 85
    assert grader.calls and reviewer.calls
    assert "独立复核" not in str(grader.calls[0])
    assert "独立复核" in str(reviewer.calls[0])


def test_plagiarism_node_only_returns_explanation_contract():
    agent = _FakeAgent({
        "explanation": "存在较高相似度，需要人工核查。",
        "review_suggestions": ["核对命中片段"],
    })
    registry = _Registry({"plagiarism_analysis": agent})

    update = create_plagiarism_node(object(), registry)({
        "frozen_result": {
            "rate": 38.5,
            "phraseRate": 42,
            "evidence": {"text": []},
        },
    })

    assert update["explanation"].explanation.startswith("存在较高")
    assert update["explanation"].model_dump() == {
        "explanation": "存在较高相似度，需要人工核查。",
        "review_suggestions": ["核对命中片段"],
    }
