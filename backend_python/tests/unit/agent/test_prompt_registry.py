"""Prompt 注册表测试：版本化注册、获取、冲突与缺失处理。"""
import pytest

from app.agent.registry import (
    TEACHER_ASSISTANT_V1,
    PromptTemplate,
    get_prompt,
    register_prompt,
)


def test_teacher_assistant_v1_registered_on_import():
    prompt = get_prompt("teacher_assistant")
    assert prompt is TEACHER_ASSISTANT_V1
    assert prompt.version == "v1"
    assert "教学助手" in prompt.content
    assert "绝不能出现" in prompt.content  # 原 SYSTEM_PROMPT 的 ID 保密规则


def test_get_prompt_by_explicit_version():
    assert get_prompt("teacher_assistant", "v1") is TEACHER_ASSISTANT_V1


def test_unknown_prompt_name_raises():
    with pytest.raises(KeyError):
        get_prompt("nonexistent_prompt")


def test_unknown_version_raises():
    with pytest.raises(KeyError):
        get_prompt("teacher_assistant", "v99")


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError):
        register_prompt(PromptTemplate(name="teacher_assistant", version="v1", content="x"))


def test_unspecified_version_returns_latest_registered():
    register_prompt(PromptTemplate(name="tmp_registry_probe", version="v1", content="一"))
    register_prompt(PromptTemplate(name="tmp_registry_probe", version="v2", content="二"))
    assert get_prompt("tmp_registry_probe").content == "二"
