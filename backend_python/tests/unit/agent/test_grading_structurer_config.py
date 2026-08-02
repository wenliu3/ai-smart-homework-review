"""可选独立结构化模型配置契约与绑定更新 Schema。"""
import pytest
from pydantic import ValidationError

from app.agent.contracts import GradingDraft, GradingReportPair, ModelProfile
from app.core.exceptions import BizException, NotFoundException
from app.crud.ai_model import get_grading_structurer_binding, set_grading_structurer_binding
from app.models import AiModel
from app.schemas.ai_model import GradingStructurerBindingUpdate

MODEL_NOT_CONFIGURED_CODE = 10016


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
    with pytest.raises(ValidationError, match="模型"):
        GradingStructurerBindingUpdate(enabled=True)
    with pytest.raises(ValidationError, match="模型"):
        GradingStructurerBindingUpdate(enabled=True, modelCode="   ")
    assert GradingStructurerBindingUpdate(enabled=True, modelCode="gpt-4o").modelCode == "gpt-4o"
    assert GradingStructurerBindingUpdate(enabled=False).modelCode is None


def _binding_flags(db, code) -> dict:
    model = db.query(AiModel).filter(AiModel.code == code).one()
    return dict(model.profile_bindings or {})


def test_grading_structurer_binding_crud(db, ai_model_factory):
    deepseek = ai_model_factory(code="deepseek")
    ai_model_factory(code="mimo", is_default=False)

    # 初始状态：未启用
    assert get_grading_structurer_binding(db) == {
        "enabled": False, "modelCode": None, "model": None,
    }

    # 启用并绑定 deepseek
    result = set_grading_structurer_binding(db, enabled=True, model_code="deepseek")
    assert result["enabled"] is True
    assert result["modelCode"] == "deepseek"
    assert result["model"]["code"] == "deepseek"
    db.expire_all()
    assert _binding_flags(db, "deepseek") == {"grading_structurer": True}
    assert _binding_flags(db, "mimo") == {}

    # 切换到 mimo：deepseek 标记被清除
    result = set_grading_structurer_binding(db, enabled=True, model_code="mimo")
    assert result["modelCode"] == "mimo"
    db.expire_all()
    assert _binding_flags(db, "deepseek") == {}
    assert _binding_flags(db, "mimo") == {"grading_structurer": True}
    assert get_grading_structurer_binding(db)["modelCode"] == "mimo"

    # 禁用：所有标记被清除
    result = set_grading_structurer_binding(db, enabled=False)
    assert result["enabled"] is False
    assert result["modelCode"] is None
    db.expire_all()
    assert _binding_flags(db, "deepseek") == {}
    assert _binding_flags(db, "mimo") == {}
    assert get_grading_structurer_binding(db)["enabled"] is False


def test_binding_rebind_same_model_is_idempotent(db, ai_model_factory):
    ai_model_factory(code="deepseek")
    ai_model_factory(code="mimo", is_default=False)

    set_grading_structurer_binding(db, enabled=True, model_code="deepseek")
    result = set_grading_structurer_binding(db, enabled=True, model_code="deepseek")
    assert result["modelCode"] == "deepseek"
    db.expire_all()
    assert _binding_flags(db, "deepseek") == {"grading_structurer": True}
    assert _binding_flags(db, "mimo") == {}
    assert get_grading_structurer_binding(db)["modelCode"] == "deepseek"


def test_binding_enable_raises_when_model_not_found(db, ai_model_factory):
    ai_model_factory(code="deepseek")
    with pytest.raises(NotFoundException) as exc:
        set_grading_structurer_binding(db, enabled=True, model_code="no-such-model")
    assert exc.value.code == 10015


def test_binding_enable_raises_when_model_inactive(db, ai_model_factory):
    ai_model_factory(code="deepseek")
    ai_model_factory(code="mimo", is_default=False, status="inactive")
    with pytest.raises(BizException) as exc:
        set_grading_structurer_binding(db, enabled=True, model_code="mimo")
    assert exc.value.code == MODEL_NOT_CONFIGURED_CODE


def test_binding_enable_raises_when_model_has_no_api_key(db, ai_model_factory):
    ai_model_factory(code="deepseek")
    ai_model_factory(code="mimo", is_default=False, api_key="")
    with pytest.raises(BizException) as exc:
        set_grading_structurer_binding(db, enabled=True, model_code="mimo")
    assert exc.value.code == MODEL_NOT_CONFIGURED_CODE
