"""管理员主管：运营、审计和模型治理路由。"""
from ..contracts import (
    AdminIntent,
    AdminIntentDecision,
    RiskLevel,
)


class AdminSupervisor:
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
        return {"intent": decision}


__all__ = ["AdminSupervisor"]
