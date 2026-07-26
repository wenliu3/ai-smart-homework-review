"""学生主管：规则优先的意图与防代写风险路由。"""
from ..contracts import (
    RiskLevel,
    StudentIntent,
    StudentIntentDecision,
)

_PROHIBITED_PATTERNS = (
    "完整答案",
    "直接给答案",
    "直接帮我写",
    "可以提交",
    "代写",
    "替我写",
)


class StudentSupervisor:
    def route(self, state: dict) -> dict:
        message = state.get("user_message", "").strip()
        lowered = message.lower()
        if any(pattern in message for pattern in _PROHIBITED_PATTERNS):
            decision = StudentIntentDecision(
                intent=StudentIntent.PROHIBITED_ANSWER,
                risk_level=RiskLevel.HIGH,
                target_agent="prohibited_answer",
                reason="请求可能形成进行中作业的完整代写答案",
            )
        elif any(word in message for word in ("评语", "反馈", "扣分", "为什么")):
            decision = StudentIntentDecision(
                intent=StudentIntent.FEEDBACK_EXPLANATION,
                target_agent="feedback_explainer",
                reason="请求解释本人已有反馈",
            )
        elif any(word in message for word in ("计划", "复习", "安排", "目标")):
            decision = StudentIntentDecision(
                intent=StudentIntent.LEARNING_PLAN,
                target_agent="learning_planner",
                reason="请求制定学习计划",
            )
        elif any(word in message for word in ("怎么做", "思路", "提示", "辅导", "学习")):
            decision = StudentIntentDecision(
                intent=StudentIntent.LEARNING_COACH,
                target_agent="learning_coach",
                reason="请求启发式学习辅导",
            )
        elif len(message) <= 20 and any(
            word in lowered for word in ("你好", "hello", "hi", "谢谢")
        ):
            decision = StudentIntentDecision(
                intent=StudentIntent.CASUAL_CHAT,
                target_agent="casual_chat",
                reason="普通寒暄",
            )
        else:
            decision = StudentIntentDecision(
                intent=StudentIntent.LEARNING_COACH,
                target_agent="learning_coach",
                reason="默认进入启发式学习辅导",
            )
        return {"intent": decision}


__all__ = ["StudentSupervisor"]
