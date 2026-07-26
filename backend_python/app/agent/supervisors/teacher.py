"""教师主 Agent：维护教师入口的结构化意图与风险决策。"""

from ..contracts import IntentDecision, RiskLevel, TeacherIntent


_WRITE_WORDS = ("发布", "删除", "修改", "改分", "打分", "创建")
_STRATEGY_WORDS = (
    "分析", "趋势", "薄弱", "教学建议", "教学策略", "改进课堂", "改进教学",
)
_CASUAL_MESSAGES = {
    "你好",
    "你好啊",
    "您好",
    "嗨",
    "hi",
    "hello",
    "你是谁",
    "你能做什么",
    "谢谢",
    "再见",
}


def route_teacher_intent(message: str) -> IntentDecision:
    """规则优先的安全路由；后续可在低风险分支接入模型分类。"""
    normalized = message.strip().lower().strip("，。！？!?,. ")
    if normalized in _CASUAL_MESSAGES or normalized.startswith("谢谢"):
        return IntentDecision(
            intent=TeacherIntent.CASUAL_CHAT,
            target_agent="casual_chat",
        )
    if any(word in message for word in _WRITE_WORDS):
        return IntentDecision(
            intent=TeacherIntent.UNSUPPORTED_WRITE,
            risk_level=RiskLevel.HIGH,
            target_agent="none",
            reason="阶段 1 仅允许只读操作",
        )
    if any(word in message for word in _STRATEGY_WORDS):
        return IntentDecision(
            intent=TeacherIntent.TEACHING_STRATEGY,
            target_agent="teacher_strategy_agent",
        )
    return IntentDecision(
        intent=TeacherIntent.TEACHING_DATA,
        target_agent="teacher_data_agent",
    )


class TeacherSupervisor:
    def route(self, state: dict) -> dict:
        return {
            "intent": route_teacher_intent(state["user_message"]),
            "visited_nodes": [*state.get("visited_nodes", []), "route"],
        }


def build_teacher_supervisor() -> TeacherSupervisor:
    """构建教师主 Agent。"""
    return TeacherSupervisor()


__all__ = [
    "TeacherSupervisor",
    "build_teacher_supervisor",
    "route_teacher_intent",
]
