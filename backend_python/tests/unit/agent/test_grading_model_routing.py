"""任务 3：网关严格按 AI 规则模型 code 路由。

init_chat_model 只构造客户端不联网；本测试 monkeypatch
app.agent.gateway.init_chat_model 捕获构造参数并返回假对象。

验证：
- 按 code 精确路由，取该模型自身 model_name 构造 LLM。
- 切换默认模型不影响按 code 路由结果（绝不回退默认模型）。
- 不存在 / inactive / 空 api_key 的 code 抛 BizException(10016)。
- 批改主/复核档位 timeout 收口为 GRADING_LLM_TIMEOUT（35 秒）。
- AgentRegistry.get_grading_agent 按 (model_code, reviewer, structured) 构建与缓存。
"""
import pytest

from app.agent.contracts import GradingDraft, ModelProfile
from app.agent.gateway import ModelGateway
from app.agent.registry import AgentRegistry
from app.agent.runtime import tool_budget_middleware
from app.core.exceptions import BizException
from app.models import AiModel


def _patch_init(monkeypatch, captured):
    """捕获 init_chat_model 的构造参数，返回假对象。"""
    monkeypatch.setattr(
        "app.agent.gateway.init_chat_model",
        lambda **kwargs: captured.append(kwargs) or object(),
    )


def _record_factory(built):
    """记录 create_agent 收到的参数，返回假 Agent。"""
    def _factory(model, tools, system_prompt, context_schema, response_format=None, middleware=None):
        built.append({
            "model": model,
            "tools": tools,
            "system_prompt": system_prompt,
            "context_schema": context_schema,
            "response_format": response_format,
            "middleware": middleware,
        })
        return object()
    return _factory


def _add_real_preset_names(db):
    """把工厂建出的模型 model_name 校正为真实预置名（deepseek-chat / mimo-v2.5）。

    ai_model_factory 默认 model_name=code；真实预置模型 code 与 model_name 不同
    （deepseek → deepseek-chat，mimo → mimo-v2.5）。这里对齐真实配置，
    用于断言按 code 路由取的是该模型自身的 model_name。只改名已存在的模型。
    """
    for code, model_name in (("deepseek", "deepseek-chat"), ("mimo", "mimo-v2.5")):
        model = db.query(AiModel).filter(AiModel.code == code).first()
        if model is not None:
            model.model_name = model_name
    db.commit()


# ========== 网关：按 code 路由 ==========

def test_routes_by_model_code(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    ai_model_factory(code="mimo", is_default=False)
    _add_real_preset_names(db)
    captured = []
    _patch_init(monkeypatch, captured)
    gw = ModelGateway()

    gw.get_chat_model_by_code(
        db, model_code="mimo", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert captured[-1]["model"] == "openai:mimo-v2.5"

    gw.get_chat_model_by_code(
        db, model_code="deepseek", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert captured[-1]["model"] == "openai:deepseek-chat"


def test_by_code_route_applies_grading_timeout(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    _add_real_preset_names(db)
    captured = []
    _patch_init(monkeypatch, captured)
    gw = ModelGateway()

    gw.get_chat_model_by_code(
        db, model_code="deepseek", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert captured[-1]["timeout"] == 35  # GRADING_LLM_TIMEOUT，不再用 VISION_GRADER 的 120
    assert captured[-1]["temperature"] == 0.2
    assert captured[-1]["max_retries"] == 1

    gw.get_chat_model_by_code(
        db, model_code="deepseek", profile=ModelProfile.REVIEWER, prompt_version="v1",
    )
    assert captured[-1]["timeout"] == 35  # 复核同样收口


def test_by_code_routing_ignores_default_flag(db, ai_model_factory, monkeypatch):
    deepseek = ai_model_factory(code="deepseek", is_default=True)
    mimo = ai_model_factory(code="mimo", is_default=False)
    _add_real_preset_names(db)
    captured = []
    _patch_init(monkeypatch, captured)
    gw = ModelGateway()

    gw.get_chat_model_by_code(
        db, model_code="mimo", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert captured[-1]["model"] == "openai:mimo-v2.5"

    # 切换默认模型（mimo 变默认、deepseek 变非默认）——按 code 路由结果必须不变
    deepseek.is_default = False
    mimo.is_default = True
    db.commit()

    gw2 = ModelGateway()
    gw2.get_chat_model_by_code(
        db, model_code="mimo", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert captured[-1]["model"] == "openai:mimo-v2.5"
    gw2.get_chat_model_by_code(
        db, model_code="deepseek", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert captured[-1]["model"] == "openai:deepseek-chat"


# ========== 网关：按 code 路由绝不回退默认 ==========

def test_nonexistent_code_raises_no_fallback(db, ai_model_factory, monkeypatch):
    # 默认模型存在且可用 —— 若实现错误回退默认，这里就不会抛异常
    ai_model_factory(code="deepseek", is_default=True)
    _patch_init(monkeypatch, [])
    gw = ModelGateway()

    with pytest.raises(BizException) as exc_info:
        gw.get_chat_model_by_code(
            db, model_code="does-not-exist",
            profile=ModelProfile.VISION_GRADER, prompt_version="v1",
        )
    assert exc_info.value.code == 10016


def test_inactive_code_raises_no_fallback(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    ai_model_factory(code="off", is_default=False, status="inactive")
    _patch_init(monkeypatch, [])
    gw = ModelGateway()

    with pytest.raises(BizException) as exc_info:
        gw.get_chat_model_by_code(
            db, model_code="off", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
        )
    assert exc_info.value.code == 10016


def test_empty_api_key_code_raises_no_fallback(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    ai_model_factory(code="nokey", is_default=False, api_key="")
    _patch_init(monkeypatch, [])
    gw = ModelGateway()

    with pytest.raises(BizException) as exc_info:
        gw.get_chat_model_by_code(
            db, model_code="nokey", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
        )
    assert exc_info.value.code == 10016


# ========== 网关：按 code 缓存与隔离 ==========

def test_by_code_chat_model_cached_and_invalidated_on_update(db, ai_model_factory, monkeypatch):
    from datetime import timedelta

    deepseek = ai_model_factory(code="deepseek", is_default=True)
    mimo = ai_model_factory(code="mimo", is_default=False)
    _add_real_preset_names(db)
    captured = []
    _patch_init(monkeypatch, captured)
    gw = ModelGateway()

    first = gw.get_chat_model_by_code(
        db, model_code="mimo", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    second = gw.get_chat_model_by_code(
        db, model_code="mimo", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert first is second
    assert len(captured) == 1

    # 更新 mimo 配置后缓存失效，重建新 LLM
    mimo.updated_at = mimo.updated_at + timedelta(seconds=1)
    db.commit()
    rebuilt = gw.get_chat_model_by_code(
        db, model_code="mimo", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert rebuilt is not first
    assert len(captured) == 2

    # 未变更的 deepseek 仍能正常按 code 路由（独立于默认模型）
    deepseek_llm = gw.get_chat_model_by_code(
        db, model_code="deepseek", profile=ModelProfile.VISION_GRADER, prompt_version="v1",
    )
    assert deepseek_llm is not None
    _ = deepseek  # 引用占位，避免未使用告警


# ========== 注册表：动态批改 Agent 工厂 ==========

def test_get_grading_agent_primary_routes_to_vision_grader(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    ai_model_factory(code="mimo", is_default=False)
    _add_real_preset_names(db)
    captured = []
    _patch_init(monkeypatch, captured)
    built = []
    gw = ModelGateway()
    registry = AgentRegistry(model_gateway=gw, agent_factory=_record_factory(built))

    registry.get_grading_agent(db, model_code="mimo", reviewer=False, structured=True)

    assert captured[-1]["model"] == "openai:mimo-v2.5"
    assert captured[-1]["timeout"] == 35
    assert built[-1]["tools"] == []
    assert built[-1]["context_schema"] is None
    assert built[-1]["response_format"] is GradingDraft
    assert built[-1]["middleware"] == [tool_budget_middleware]
    assert "结构化批改" in built[-1]["system_prompt"]  # grading_specialist Prompt


def test_get_grading_agent_review_routes_to_reviewer(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    _add_real_preset_names(db)
    captured = []
    _patch_init(monkeypatch, captured)
    built = []
    gw = ModelGateway()
    registry = AgentRegistry(model_gateway=gw, agent_factory=_record_factory(built))

    registry.get_grading_agent(db, model_code="deepseek", reviewer=True, structured=True)

    assert captured[-1]["model"] == "openai:deepseek-chat"
    assert captured[-1]["temperature"] == 0.1  # REVIEWER 档位
    assert captured[-1]["timeout"] == 35
    assert built[-1]["response_format"] is GradingDraft
    assert "独立批改复核" in built[-1]["system_prompt"]  # grading_review_specialist Prompt


def test_get_grading_agent_unstructured_omits_response_format(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    _add_real_preset_names(db)
    _patch_init(monkeypatch, [])
    built = []
    gw = ModelGateway()
    registry = AgentRegistry(model_gateway=gw, agent_factory=_record_factory(built))

    registry.get_grading_agent(db, model_code="deepseek", reviewer=False, structured=False)
    assert built[-1]["response_format"] is None


def test_get_grading_agent_caches_by_code_reviewer_structured(db, ai_model_factory, monkeypatch):
    ai_model_factory(code="deepseek", is_default=True)
    ai_model_factory(code="mimo", is_default=False)
    _add_real_preset_names(db)
    _patch_init(monkeypatch, [])
    built = []
    gw = ModelGateway()
    registry = AgentRegistry(model_gateway=gw, agent_factory=_record_factory(built))

    a1 = registry.get_grading_agent(db, model_code="mimo", reviewer=False, structured=True)
    a2 = registry.get_grading_agent(db, model_code="mimo", reviewer=False, structured=True)
    assert a1 is a2
    assert len(built) == 1

    b = registry.get_grading_agent(db, model_code="mimo", reviewer=True, structured=True)
    assert b is not a1
    assert len(built) == 2

    c = registry.get_grading_agent(db, model_code="deepseek", reviewer=False, structured=True)
    assert c is not a1 and c is not b
    assert len(built) == 3
