import pytest
from pydantic import ValidationError

from app.agent.contracts import GradingDraft, GradingReportPair, ModelProfile
from app.schemas.ai_model import GradingStructurerBindingUpdate


def test_grading_structurer_profile_and_pair_contract():
    assert ModelProfile.GRADING_STRUCTURER.value == "grading_structurer"
    payload = {
        "schema_version": "v1",
        "primary": {
            "rubric_version": "rubric-v1",
            "items": [{
                "criterion_id": "overall",
                "title": "综合质量",
                "score": 86,
                "max_score": 100,
                "feedback": "完成主要任务",
                "evidence_refs": ["submission:attachment:1"],
            }],
            "summary": "主批改报告",
        },
        "review": {
            "rubric_version": "rubric-v1",
            "items": [{
                "criterion_id": "overall",
                "title": "综合质量",
                "score": 82,
                "max_score": 100,
                "feedback": "部分分析不足",
                "evidence_refs": ["submission:attachment:1"],
            }],
            "summary": "独立复核报告",
        },
    }
    pair = GradingReportPair.model_validate(payload)
    assert isinstance(pair.primary, GradingDraft)
    assert pair.review.total_score == 82


def test_structurer_binding_requires_model_when_enabled():
    with pytest.raises(ValidationError):
        GradingStructurerBindingUpdate(enabled=True)
    assert GradingStructurerBindingUpdate(enabled=False).modelCode is None
