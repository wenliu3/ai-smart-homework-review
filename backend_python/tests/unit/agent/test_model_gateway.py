"""ModelGateway 测试：默认配置解析、多维缓存键、档位参数、密钥脱敏。

init_chat_model 只构造 ChatOpenAI 客户端对象，不发起网络请求，可安全断言。
"""
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.agent.contracts import ModelProfile
from app.agent.services.model_gateway import ModelGateway, mask_secret
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


def test_mask_secret():
    assert mask_secret("sk-1234567890abcd") == "sk-1****abcd"
    assert mask_secret("short") == "****"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
