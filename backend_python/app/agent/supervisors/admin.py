"""管理员主管：运营、审计和模型治理路由。"""
from ..contracts import (
    AdminIntent,
    AdminIntentDecision,
    RiskLevel,
)


_LLM_LABEL_DECISIONS = {
    "casual_chat": lambda: AdminIntentDecision(
        intent=AdminIntent.CASUAL_CHAT,
        target_agent="admin_casual_chat",
        reason="llm_router 兜底分类",
    ),
    "operations_analysis": lambda: AdminIntentDecision(
        intent=AdminIntent.OPERATIONS_ANALYSIS,
        target_agent="operations_analysis_agent",
        reason="llm_router 兜底分类",
    ),
    "audit_analysis": lambda: AdminIntentDecision(
        intent=AdminIntent.AUDIT_ANALYSIS,
        risk_level=RiskLevel.MEDIUM,
        target_agent="audit_analysis_agent",
        reason="llm_router 兜底分类",
    ),
    # LLM 兜底产生的模型治理意图不带 requires_approval：写路径只靠关键词
    "model_governance": lambda: AdminIntentDecision(
        intent=AdminIntent.MODEL_GOVERNANCE,
        target_agent="model_governance_agent",
        reason="llm_router 兜底分类",
    ),
}


class AdminSupervisor:
    def __init__(self, route_classifier=None) -> None:
        # 关键词未命中时的单次 LLM 分类兜底（规划 5.1）；None 保持纯关键词
        self._route_classifier = route_classifier

    def route(self, state: dict) -> dict:
        message = state.get("user_message", "").strip()
        if any(word in message for word in (
            "切换模型", "默认模型", "修改模型", "更新配置", "启用模型", "停用模型",
        )):
            decision = AdminIntentDecision(
                intent=AdminIntent.MODEL_GOVERNANCE,
                risk_level=RiskLevel.HIGH,
                target_agent="model_governance_agent",
                reason="模型配置变更属于受控写操作",
                requires_approval=True,
            )
        elif any(word in message for word in (
            "审计", "异常", "失败", "越权", "安全", "日志",
        )):
            decision = AdminIntentDecision(
                intent=AdminIntent.AUDIT_ANALYSIS,
                risk_level=RiskLevel.MEDIUM,
                target_agent="audit_analysis_agent",
                reason="请求聚合审计分析",
            )
        elif len(message) <= 20 and any(
            word in message.lower() for word in ("你好", "hello", "hi", "谢谢")
        ):
            decision = AdminIntentDecision(
                intent=AdminIntent.CASUAL_CHAT,
                target_agent="admin_casual_chat",
                reason="普通寒暄",
            )
        elif any(word in message for word in (
            "模型", "成本", "token", "用量", "治理",
        )):
            decision = AdminIntentDecision(
                intent=AdminIntent.MODEL_GOVERNANCE,
                target_agent="model_governance_agent",
                reason="请求模型治理分析",
            )
        else:
            decision = AdminIntentDecision(
                intent=AdminIntent.OPERATIONS_ANALYSIS,
                target_agent="operations_analysis_agent",
                reason="请求平台聚合运营分析",
            )
            if self._route_classifier is not None:
                try:
                    label = self._route_classifier(message)
                except Exception:
                    label = None
                builder = _LLM_LABEL_DECISIONS.get(label or "")
                if builder is not None:
                    decision = builder()
        return {"intent": decision}


__all__ = ["AdminSupervisor"]
