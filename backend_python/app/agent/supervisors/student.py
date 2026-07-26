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


_LLM_LABEL_DECISIONS = {
    "casual_chat": lambda: StudentIntentDecision(
        intent=StudentIntent.CASUAL_CHAT,
        target_agent="casual_chat",
        reason="llm_router 兜底分类",
    ),
    "learning_coach": lambda: StudentIntentDecision(
        intent=StudentIntent.LEARNING_COACH,
        target_agent="learning_coach",
        reason="llm_router 兜底分类",
    ),
    "feedback_explanation": lambda: StudentIntentDecision(
        intent=StudentIntent.FEEDBACK_EXPLANATION,
        target_agent="feedback_explainer",
        reason="llm_router 兜底分类",
    ),
    "learning_plan": lambda: StudentIntentDecision(
        intent=StudentIntent.LEARNING_PLAN,
        target_agent="learning_planner",
        reason="llm_router 兜底分类",
    ),
    "prohibited_answer": lambda: StudentIntentDecision(
        intent=StudentIntent.PROHIBITED_ANSWER,
        risk_level=RiskLevel.HIGH,
        target_agent="prohibited_answer",
        reason="llm_router 判定疑似代写请求",
    ),
}


class StudentSupervisor:
    def __init__(
        self,
        route_classifier=None,
        topic_similarity_checker=None,
    ) -> None:
        # 关键词未命中时的单次 LLM 分类兜底（规划 5.1）；None 保持纯关键词
        self._route_classifier = route_classifier
        # 题面相似度检查（规划 5.2）：请求与进行中作业题面高度重合时
        # 升级为 PROHIBITED_ANSWER；检查失败不阻塞正常路由
        self._topic_checker = topic_similarity_checker

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
            if self._route_classifier is not None:
                try:
                    label = self._route_classifier(message)
                except Exception:
                    label = None
                builder = _LLM_LABEL_DECISIONS.get(label or "")
                if builder is not None:
                    decision = builder()
        if (
            self._topic_checker is not None
            and decision.intent not in (
                StudentIntent.PROHIBITED_ANSWER,
                StudentIntent.CASUAL_CHAT,
            )
        ):
            try:
                actor = state.get("actor")
                student_id = getattr(actor, "user_id", 0)
                if self._topic_checker(message, student_id):
                    decision = StudentIntentDecision(
                        intent=StudentIntent.PROHIBITED_ANSWER,
                        risk_level=RiskLevel.HIGH,
                        target_agent="prohibited_answer",
                        reason="请求与进行中作业题面高度重合，疑似代写",
                    )
            except Exception:
                pass
        return {"intent": decision}


__all__ = ["StudentSupervisor"]
