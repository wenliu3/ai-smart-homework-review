"""可选独立结构化模型配置契约与绑定更新 Schema。"""
import pytest
from langchain.agents.structured_output import StructuredOutputError
from pydantic import ValidationError

from app.agent.contracts import GradingDraft, GradingReportPair, ModelProfile
from app.agent.registry import agent_registry
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


# ========== 任务 9：结构化输出能力测试端点 ==========

@pytest.fixture()
def superadmin(user_factory):
    return user_factory("admin_root", "superadmin")


def _capability_pair_payload() -> dict:
    """固定最小 GradingReportPair 负载（不含任何真实作业/学生数据）。"""

    def _draft(score: float, summary: str, feedback: str) -> dict:
        return {
            "schema_version": "v1",
            "rubric_version": "rubric-v1",
            "items": [{
                "criterion_id": "overall",
                "title": "综合质量",
                "score": score,
                "max_score": 100,
                "feedback": feedback,
                "evidence_refs": ["test:placeholder:1"],
            }],
            "summary": summary,
            "limitations": [],
            "confidence": None,
            "requires_human_review": False,
            "review_reasons": [],
        }

    return {
        "primary": _draft(86, "主批改占位草案", "内容完整，依据充分。"),
        "review": _draft(82, "独立复核占位草案", "内容较完整，个别依据不足。"),
    }


class _CapabilityAgent:
    """替身结构化 Agent：记录调用与传入消息，返回预设结果。"""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(self, payload, **kwargs):
        self.calls.append((payload, kwargs))
        return self.result


def test_structurer_capability_test_success_uses_selected_model(
    client, superadmin, auth_header, ai_model_factory, monkeypatch,
):
    """能力测试成功：只使用管理员选中的模型，不读取学生/作业数据。"""
    ai_model_factory(code="deepseek")
    agent = _CapabilityAgent({"structured_response": _capability_pair_payload()})
    requested = []

    def fake_get_structurer_agent(db, *, model_code):
        requested.append(model_code)
        return agent

    monkeypatch.setattr(agent_registry, "get_structurer_agent", fake_get_structurer_agent)

    resp = client.post(
        "/api/admin/ai-models/deepseek/test-structured-output",
        headers=auth_header(superadmin),
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert data["modelCode"] == "deepseek"
    assert data["message"] == "结构化输出能力验证通过"
    assert isinstance(data.get("responseTime"), int)
    # 只用管理员选中的模型，且只调用一次
    assert requested == ["deepseek"]
    assert len(agent.calls) == 1
    payload, kwargs = agent.calls[0]
    content = payload["messages"][0].content
    assert "结构化输出能力测试" in content
    # 固定无业务数据 Prompt：绝不包含学生/作业/证据引用
    assert "学生" not in content
    assert "作业" not in content
    assert "submission" not in content.lower()
    assert kwargs["config"]["recursion_limit"] == 2


def test_structurer_capability_test_failure_summary_not_raw(
    client, superadmin, auth_header, ai_model_factory, monkeypatch,
):
    """失败只返回截断错误摘要，绝不返回模型原始输出。"""
    ai_model_factory(code="deepseek")

    class _BadOutputAgent:
        def invoke(self, payload, **kwargs):
            return {"structured_response": {
                "primary": "RAW_GARBAGE_001",
                "review": "RAW_SECRET_002",
            }}

    monkeypatch.setattr(
        agent_registry, "get_structurer_agent",
        lambda db, *, model_code: _BadOutputAgent(),
    )

    resp = client.post(
        "/api/admin/ai-models/deepseek/test-structured-output",
        headers=auth_header(superadmin),
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is False
    assert data["modelCode"] == "deepseek"
    assert data["message"]
    assert isinstance(data.get("responseTime"), int)
    assert "RAW_GARBAGE_001" not in resp.text
    assert "RAW_SECRET_002" not in resp.text
    assert "structured_response" not in resp.text


def test_structurer_capability_test_failure_keeps_binding(
    client, superadmin, auth_header, ai_model_factory, monkeypatch, db,
):
    """能力测试失败不改变结构化绑定状态。"""
    ai_model_factory(code="deepseek")
    ai_model_factory(code="mimo", is_default=False)
    set_grading_structurer_binding(db, enabled=True, model_code="deepseek")

    class _RaisingAgent:
        def invoke(self, payload, **kwargs):
            raise StructuredOutputError("模型未返回结构化输出")

    monkeypatch.setattr(
        agent_registry, "get_structurer_agent",
        lambda db, *, model_code: _RaisingAgent(),
    )

    # 对未绑定的 mimo 跑能力测试：绑定状态必须保持 deepseek
    resp = client.post(
        "/api/admin/ai-models/mimo/test-structured-output",
        headers=auth_header(superadmin),
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is False
    assert data["modelCode"] == "mimo"
    assert "模型未返回结构化输出" in data["message"]

    binding = get_grading_structurer_binding(db)
    assert binding["enabled"] is True
    assert binding["modelCode"] == "deepseek"


def test_structurer_capability_test_inactive_model_no_agent_call(
    client, superadmin, auth_header, ai_model_factory, monkeypatch,
):
    """未启用/无 Key 的模型直接返回 success=false，不触发 Agent 调用。"""
    ai_model_factory(code="deepseek", status="inactive")
    called = []

    def fake_get_structurer_agent(db, *, model_code):
        called.append(model_code)
        raise AssertionError("不应为未启用模型构建 Agent")

    monkeypatch.setattr(agent_registry, "get_structurer_agent", fake_get_structurer_agent)

    resp = client.post(
        "/api/admin/ai-models/deepseek/test-structured-output",
        headers=auth_header(superadmin),
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is False
    assert data["modelCode"] == "deepseek"
    assert data["message"]
    assert called == []
