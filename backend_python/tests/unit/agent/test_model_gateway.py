"""ModelGateway 测试：默认配置解析、多维缓存键、档位参数、密钥脱敏。

init_chat_model 只构造 ChatOpenAI 客户端对象，不发起网络请求，可安全断言。
"""
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.agent.contracts import ModelProfile
from app.agent.gateway import PROFILE_SETTINGS, ModelGateway, mask_secret
from app.core.exceptions import BizException
from app.models import AiModel


def test_raises_when_no_model_configured(db):
    gw = ModelGateway()
    with pytest.raises(BizException) as exc_info:
        gw.get_default_config(db)
    assert exc_info.value.code == 10016
    assert "没有可用的 AI 模型" in exc_info.value.message


def test_raises_when_default_model_has_no_api_key(db, ai_model_factory):
    ai_model_factory(api_key="")
    gw = ModelGateway()
    with pytest.raises(BizException) as exc_info:
        gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert "未配置 API Key" in exc_info.value.message


def test_falls_back_to_active_model_when_no_default(db, ai_model_factory):
    m = ai_model_factory(is_default=False, status="active")
    gw = ModelGateway()
    assert gw.get_default_config(db).id == m.id


def test_prefers_default_over_other_active(db, ai_model_factory):
    ai_model_factory(code="m-plain", is_default=False)
    default = ai_model_factory(code="m-default", is_default=True)
    gw = ModelGateway()
    assert gw.get_default_config(db).id == default.id


def test_inactive_default_falls_back_to_active_model(db, ai_model_factory):
    ai_model_factory(
        code="m-disabled-default",
        is_default=True,
        status="inactive",
    )
    active = ai_model_factory(
        code="m-active",
        is_default=False,
        status="active",
    )
    gw = ModelGateway()

    assert gw.get_default_config(db).id == active.id


def test_chat_model_cached_by_key(db, ai_model_factory):
    ai_model_factory()
    gw = ModelGateway()
    first = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    second = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert first is second


def test_cache_key_includes_profile(db, ai_model_factory):
    ai_model_factory()
    gw = ModelGateway()
    general = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    router = gw.get_chat_model(db, ModelProfile.ROUTER, prompt_version="v1")
    assert general is not router


def test_cache_invalidated_when_model_updated(db, ai_model_factory):
    m = ai_model_factory()
    gw = ModelGateway()
    first = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    # 模拟管理员更新配置：updated_at 前进 1 秒（server onupdate 为秒级精度）
    db.execute(
        update(AiModel)
        .where(AiModel.id == m.id)
        .values(updated_at=m.updated_at + timedelta(seconds=1))
    )
    db.commit()
    second = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert second is not first


def test_profile_temperature_settings(db, ai_model_factory):
    ai_model_factory()
    gw = ModelGateway()
    router_llm = gw.get_chat_model(db, ModelProfile.ROUTER, prompt_version="v1")
    general_llm = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")
    assert router_llm.temperature == 0.1
    assert general_llm.temperature == 0.3
    assert general_llm.max_tokens == 2000


def test_interactive_profile_timeouts_fit_the_default_run_budget():
    assert PROFILE_SETTINGS[ModelProfile.ROUTER]["timeout"] <= 45
    assert PROFILE_SETTINGS[ModelProfile.GENERAL]["timeout"] <= 45
    assert PROFILE_SETTINGS[ModelProfile.REVIEWER]["timeout"] <= 45


def test_mask_secret():
    assert mask_secret("sk-1234567890abcd") == "sk-1****abcd"
    assert mask_secret("short") == "****"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""


def test_model_creation_log_never_contains_api_key_fragments(
    db,
    ai_model_factory,
    caplog,
):
    api_key = "sk-visible-prefix-and-secret-tail"
    ai_model_factory(api_key=api_key)
    gw = ModelGateway()

    with caplog.at_level("INFO"):
        gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")

    assert api_key[:4] not in caplog.text
    assert api_key[-4:] not in caplog.text


def test_deepseek_v4_llm_disables_thinking_for_tool_choice(db, ai_model_factory):
    """DeepSeek V4 默认 thinking 不支持强制 tool_choice，网关应经 extra_body 关闭 thinking。"""
    ai_model_factory(code="deepseek-v4-flash")
    gw = ModelGateway()

    llm = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")

    assert (llm.extra_body or {}).get("thinking") == {"type": "disabled"}


def test_non_v4_model_has_no_thinking_kwargs(db, ai_model_factory):
    """非 DeepSeek V4 且非智谱的模型（如 deepseek-chat）不注入 thinking 参数。"""
    ai_model_factory(code="deepseek-chat")
    gw = ModelGateway()

    llm = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")

    assert "thinking" not in (llm.extra_body or {})


def test_zhipu_glm_llm_uses_low_reasoning_effort(db, ai_model_factory):
    """智谱 GLM-5.3 系列强制思考且不支持 disabled，网关应注入 reasoning_effort=low。"""
    ai_model_factory(code="zhipu")
    db.query(AiModel).filter(AiModel.code == "zhipu").update(
        {AiModel.provider: "智谱", AiModel.model_name: "glm-5.3-flash"}
    )
    db.commit()
    gw = ModelGateway()

    llm = gw.get_chat_model(db, ModelProfile.GENERAL, prompt_version="v1")

    assert (llm.extra_body or {}).get("reasoning_effort") == "low"
    assert (llm.extra_body or {}).get("thinking") == {"type": "enabled"}
