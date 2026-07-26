import pytest
from pydantic import ValidationError

from app.agent.contracts import PlagiarismExplanation
from app.agent.graphs.plagiarism import build_plagiarism_graph
from app.crud import plagiarism_suggestion


def _engine_result():
    return {
        "rate": 38.5,
        "phraseRate": 42.0,
        "topicRate": 21.5,
        "imageRate": 12.0,
        "matchedImageCount": 1,
        "status": "warning",
        "evidence": {
            "text": [{"snippet": "重复文本"}],
            "image": [{"hash": "abc"}],
            "template": [{"snippet": "课程模板"}],
            "common": [{"snippet": "公共定义"}],
        },
    }


def test_plagiarism_graph_preserves_engine_metrics_and_evidence_exactly():
    source = _engine_result()

    def explain(state):
        return {
            "explanation": PlagiarismExplanation(
                explanation="重复率偏高，建议人工核对命中片段。",
                review_suggestions=["核对引用格式", "检查公共模板影响"],
            ),
        }

    result = build_plagiarism_graph(explain).invoke({
        "deterministic_result": source,
    })

    assert result["analysis"].deterministic_result == source
    assert result["analysis"].deterministic_result["evidence"] == source["evidence"]
    assert result["analysis"].explanation.explanation.startswith("重复率偏高")


def test_plagiarism_explanation_contract_forbids_violation_verdict_and_metrics():
    with pytest.raises(ValidationError):
        PlagiarismExplanation.model_validate({
            "explanation": "判定抄袭",
            "review_suggestions": [],
            "violation": True,
            "rate": 99,
        })


def test_legacy_suggestion_api_uses_new_graph_without_changing_metrics(
    monkeypatch,
):
    captured = {}

    def fake_node(state):
        captured["result"] = state["frozen_result"]
        return {"explanation": {
            "explanation": "建议人工检查引用标注。",
            "review_suggestions": ["核对命中片段"],
        }}

    monkeypatch.setattr(
        plagiarism_suggestion,
        "create_plagiarism_node",
        lambda db: fake_node,
    )
    from app.agent.contracts import ReviewResult

    monkeypatch.setattr(
        plagiarism_suggestion,
        "create_plagiarism_review_node",
        lambda db: lambda state: {
            "review": ReviewResult(approved=True, issues=[]),
        },
    )
    source = _engine_result()

    text = plagiarism_suggestion.generate_plagiarism_suggestion(
        object(),
        student_name="学生",
        student_number="S001",
        content="正文",
        plagiarism_info=source,
        submission_id=7,
        actor_user_id=11,
    )

    assert captured["result"] == source
    assert "建议人工检查引用标注" in text
    assert "核对命中片段" in text
