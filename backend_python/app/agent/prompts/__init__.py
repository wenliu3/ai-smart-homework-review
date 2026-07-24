from .registry import PromptTemplate, get_prompt, register_prompt
from . import teacher_assistant  # noqa: F401  导入即注册

__all__ = ["PromptTemplate", "get_prompt", "register_prompt"]
