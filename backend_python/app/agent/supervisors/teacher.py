"""教师主 Agent：维护教师入口的结构化意图与风险决策。"""

import re

from ..contracts import IntentDecision, RiskLevel, TeacherIntent


# 只收明确的动作动词。「评分」「调整」「更新」这类在只读提问里常作名词
# （评分标准 / 评分分布 / 调整讲解重点），收进来会大面积误判，故刻意不收。
_WRITE_WORDS = (
    "发布", "上线", "下架", "终止",
    "删除", "移除",
    "修改", "编辑",
    "改分", "打分", "给分",
    "创建", "新建",
)
# 疑问句式：命中即视为只读提问，写意图词只是被当成名词提到。
# 放在写意图判定之前，避免「哪些作业还没发布」这类被判成写请求。
_QUESTION_PREFIXES = (
    "哪些", "哪个", "哪几", "什么", "多少", "怎么", "如何", "为什么",
    "是否", "有没有", "能不能", "可不可以", "谁",
)
_QUESTION_SUFFIXES = ("吗", "呢", "吧", "?", "？")
# 已登记审批白名单的写操作对象（对照 crud/action_execution.py:_ROLE_ACTIONS）
_SUPPORTED_WRITE_TARGETS = (
    "作业", "提交", "批改", "分数", "得分", "成绩", "评分", "规则", "量表",
)
# 高风险写操作对象：规划 D1 明确列为本轮范围外，必须拒绝而非产出草案
_UNSUPPORTED_WRITE_TARGETS = (
    "班级", "学生", "用户", "账号", "账户", "教师", "密码", "权限", "角色", "模型",
)
# 「打 85 分」这类不含固定动词组合的改分表达
_SCORE_PATTERN = re.compile(r"[打给评改加扣]\s*\d+(?:\.\d+)?\s*分")
# 创建作业草稿的自然语言表达：不依赖固定的「创建/新建」二字，且允许描述里出现
# 「班级」（如「自然语言处理的班级」）——它是作业的属性描述，不是被删除的对象。
# 疑问句会先被 _is_question 拦截，因此这里只需覆盖祈使/陈述句。
_DRAFT_CREATE_PATTERN = re.compile(
    r"(?:帮我|请|给我|帮)?\s*"
    r"(?:起草|起个|创建|新建|生成|做个|做一个)"
    r".{0,16}"
    r"(?:作业|规则|量表)"
    r"(?:草稿)?"
)
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


def _is_question(message: str) -> bool:
    """疑问句式检测：教师在问情况，而不是在下达写操作指令。"""
    stripped = message.strip()
    return (
        any(word in stripped for word in _QUESTION_PREFIXES)
        or stripped.endswith(_QUESTION_SUFFIXES)
    )


def _is_write_request(message: str) -> bool:
    if _is_question(message):
        return False
    return (
        any(word in message for word in _WRITE_WORDS)
        or _DRAFT_CREATE_PATTERN.search(message) is not None
        or _SCORE_PATTERN.search(message) is not None
    )


def _route_write_decision(message: str) -> IntentDecision:
    """写请求意图细分：创建草稿优先，其次高风险对象拒绝，最后白名单对象产出草案。"""
    # 创建草稿意图先于高风险对象判定：描述里出现「班级」只表示作业关联班级，
    # 不是要删除班级本身（如「是自然语言处理的班级」）。疑问句已在上游被拦截。
    if _DRAFT_CREATE_PATTERN.search(message) is not None:
        return IntentDecision(
            intent=TeacherIntent.ACTION_DRAFT,
            risk_level=RiskLevel.HIGH,
            target_agent="teacher_action_agent",
            reason="创建草稿意图，需产出待审批草案",
        )
    if any(word in message for word in _UNSUPPORTED_WRITE_TARGETS):
        return IntentDecision(
            intent=TeacherIntent.UNSUPPORTED_WRITE,
            risk_level=RiskLevel.HIGH,
            target_agent="none",
            reason="该对象的写操作不在审批白名单内",
        )
    if any(word in message for word in _SUPPORTED_WRITE_TARGETS):
        return IntentDecision(
            intent=TeacherIntent.ACTION_DRAFT,
            risk_level=RiskLevel.HIGH,
            target_agent="teacher_action_agent",
            reason="受支持的写操作，需产出待审批草案",
        )
    # 目标对象无法识别时不猜测，保守拒绝
    return IntentDecision(
        intent=TeacherIntent.UNSUPPORTED_WRITE,
        risk_level=RiskLevel.HIGH,
        target_agent="none",
        reason="写操作目标不明确",
    )


def route_teacher_intent(message: str) -> IntentDecision:
    """规则优先的安全路由；后续可在低风险分支接入模型分类。"""
    normalized = message.strip().lower().strip("，。！？!?,. ")
    if normalized in _CASUAL_MESSAGES or normalized.startswith("谢谢"):
        return IntentDecision(
            intent=TeacherIntent.CASUAL_CHAT,
            target_agent="casual_chat",
        )
    if _is_write_request(message):
        return _route_write_decision(message)
    if any(word in message for word in _STRATEGY_WORDS):
        return IntentDecision(
            intent=TeacherIntent.TEACHING_STRATEGY,
            target_agent="teacher_strategy_agent",
        )
    return IntentDecision(
        intent=TeacherIntent.TEACHING_DATA,
        target_agent="teacher_data_agent",
    )


_LLM_LABEL_DECISIONS = {
    "casual_chat": lambda: IntentDecision(
        intent=TeacherIntent.CASUAL_CHAT,
        target_agent="casual_chat",
        reason="llm_router 兜底分类",
    ),
    "teaching_data": lambda: IntentDecision(
        intent=TeacherIntent.TEACHING_DATA,
        target_agent="teacher_data_agent",
        reason="llm_router 兜底分类",
    ),
    "teaching_strategy": lambda: IntentDecision(
        intent=TeacherIntent.TEACHING_STRATEGY,
        target_agent="teacher_strategy_agent",
        reason="llm_router 兜底分类",
    ),
}


class TeacherSupervisor:
    def __init__(self, route_classifier=None) -> None:
        # 关键词未命中时的单次 LLM 分类兜底（规划 5.1）；None 保持纯关键词
        self._route_classifier = route_classifier

    def route(self, state: dict) -> dict:
        message = state["user_message"]
        decision = route_teacher_intent(message)
        # 「未命中」= 落到 TEACHING_DATA 默认分支（无 reason 的兜底路径）
        keyword_miss = (
            decision.intent == TeacherIntent.TEACHING_DATA
            and not decision.reason
        )
        if keyword_miss and self._route_classifier is not None:
            try:
                label = self._route_classifier(message)
            except Exception:
                label = None
            builder = _LLM_LABEL_DECISIONS.get(label or "")
            if builder is not None:
                decision = builder()
        return {
            "intent": decision,
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
