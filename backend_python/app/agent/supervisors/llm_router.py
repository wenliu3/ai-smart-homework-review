"""LLM 路由兜底（规划阶段 5.1）。

关键词未命中时用 ROUTER 档位模型做一次意图分类（规格允许最多一次）：
- 分类器只在主管默认分支被调用，命中关键词绝不调用。
- 标签白名单按角色收紧：教师写意图（action_draft）不给 LLM——
  写路径只能由确定性关键词开启；学生 prohibited_answer 保留给 LLM，
  改写代写请求被兜底拦截属于安全增强。
- 任何异常/非法标签都回退关键词默认值，绝不阻塞路由。
"""
from __future__ import annotations

import logging
from typing import Callable

from langchain_core.messages import HumanMessage

from ..contracts import ModelProfile

logger = logging.getLogger(__name__)

ROLE_ROUTE_LABELS: dict[str, set[str]] = {
    "teacher": {"casual_chat", "teaching_data", "teaching_strategy"},
    "student": {
        "casual_chat",
        "learning_coach",
        "feedback_explanation",
        "learning_plan",
        "prohibited_answer",
    },
    "superadmin": {
        "casual_chat",
        "operations_analysis",
        "audit_analysis",
        "model_governance",
    },
}


def parse_route_label(raw, *, role: str) -> str | None:
    """严格解析模型输出：小写、去引号空白，白名单外一律 None。"""
    if not isinstance(raw, str):
        return None
    label = raw.strip().strip('"').strip("'").strip().lower()
    if label in ROLE_ROUTE_LABELS.get(role, set()):
        return label
    return None


def create_route_classifier(db, role: str) -> Callable[[str], str | None]:
    """构造单次 LLM 意图分类器（惰性取 ROUTER 档位模型）。

    返回的可调用对象：输入用户消息，输出白名单标签或 None。
    模型不可用/超时/输出非法都返回 None，由主管回退关键词默认。
    """
    labels = sorted(ROLE_ROUTE_LABELS[role])

    def classify(message: str) -> str | None:
        try:
            from ..gateway import model_gateway

            llm = model_gateway.get_chat_model(db, ModelProfile.ROUTER)
            prompt = (
                "把下面这条用户消息分类到且仅到一个意图标签。"
                f"可选标签：{', '.join(labels)}。"
                "只输出标签本身，不要输出其他任何内容。\n"
                f"用户消息：{message[:500]}"
            )
            result = llm.invoke([HumanMessage(content=prompt)])
            return parse_route_label(
                getattr(result, "content", None), role=role,
            )
        except Exception:
            logger.warning("LLM 路由兜底失败，回退关键词默认", exc_info=True)
            return None

    return classify


__all__ = [
    "ROLE_ROUTE_LABELS",
    "create_route_classifier",
    "parse_route_label",
]
