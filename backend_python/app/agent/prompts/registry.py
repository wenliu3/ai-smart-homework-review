"""Prompt 版本注册表（规格 11.3）。

系统 Prompt 以代码文件管理并带显式版本（如 teacher_assistant:v1）；
教师创建的 AiRule.prompt 是业务评分规则，不经过本注册表；
核心安全 Prompt 不允许在生产界面直接编辑。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    content: str


_REGISTRY: dict[str, dict[str, PromptTemplate]] = {}


def register_prompt(prompt: PromptTemplate) -> PromptTemplate:
    """注册 Prompt；同名同版本重复注册视为配置错误，直接拒绝。"""
    versions = _REGISTRY.setdefault(prompt.name, {})
    if prompt.version in versions:
        raise ValueError(f"Prompt 已注册: {prompt.name}:{prompt.version}")
    versions[prompt.version] = prompt
    return prompt


def get_prompt(name: str, version: str | None = None) -> PromptTemplate:
    """获取 Prompt；version 为 None 时返回最后注册的版本（dict 保序）。"""
    versions = _REGISTRY.get(name)
    if not versions:
        raise KeyError(f"未注册的 Prompt: {name}")
    if version is None:
        return list(versions.values())[-1]
    try:
        return versions[version]
    except KeyError:
        raise KeyError(f"Prompt {name} 没有版本 {version}") from None
