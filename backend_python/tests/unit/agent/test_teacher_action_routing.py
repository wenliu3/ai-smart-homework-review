"""教师写意图路由与写操作契约（规划阶段 3A.1 / 3A.2）。

覆盖：
- 受支持写操作（作业/评分/规则）路由到 ACTION_DRAFT。
- 高风险对象（班级/学生/账号）仍然拒绝为 UNSUPPORTED_WRITE。
- 目标不明确的写请求保守拒绝。
- 只读意图不被写意图规则误伤。
"""
import pytest

from app.agent.contracts import ActionType, RiskLevel, TeacherIntent
from app.agent.supervisors.teacher import route_teacher_intent


# ========== 契约 ==========

def test_teacher_intent_has_action_draft():
    assert TeacherIntent.ACTION_DRAFT.value == "action_draft"
    # 保留：范围外的高风险写操作仍需明确拒绝
    assert TeacherIntent.UNSUPPORTED_WRITE.value == "unsupported_write"


def test_action_type_covers_assignment_lifecycle():
    assert ActionType.PUBLISH_ASSIGNMENT.value == "publish_assignment"
    assert ActionType.UPDATE_ASSIGNMENT.value == "update_assignment"
    assert ActionType.DELETE_ASSIGNMENT.value == "delete_assignment"


# ========== 受支持的写意图 → ACTION_DRAFT ==========

@pytest.mark.parametrize("message", [
    "直接发布这份作业",
    "帮我发布一份作业",
    "把数据结构作业的截止时间修改为下周五",
    "删除那份还没人提交的作业",
    "帮我给张三的作业打 85 分",
    "给这份提交评 90 分",
    "创建一条新的 AI 批改规则",
])
def test_supported_write_requests_route_to_action_draft(message):
    decision = route_teacher_intent(message)

    assert decision.intent == TeacherIntent.ACTION_DRAFT
    assert decision.target_agent == "teacher_action_agent"
    assert decision.risk_level == RiskLevel.HIGH


# ========== 范围外的写意图 → UNSUPPORTED_WRITE ==========

@pytest.mark.parametrize("message", [
    "删除这个班级",
    "把李四这个学生移除",
    "修改王五的账号密码",
    "创建一个新的教师用户",
])
def test_high_risk_write_targets_stay_unsupported(message):
    decision = route_teacher_intent(message)

    assert decision.intent == TeacherIntent.UNSUPPORTED_WRITE
    assert decision.risk_level == RiskLevel.HIGH


def test_write_request_without_recognizable_target_is_refused():
    decision = route_teacher_intent("帮我删除一下")

    assert decision.intent == TeacherIntent.UNSUPPORTED_WRITE


# ========== 只读意图不被误伤 ==========

@pytest.mark.parametrize("message,expected", [
    ("查看我的班级", TeacherIntent.TEACHING_DATA),
    ("待批改有多少份", TeacherIntent.TEACHING_DATA),
    ("分析最近成绩趋势", TeacherIntent.TEACHING_STRATEGY),
    ("给我分层教学建议", TeacherIntent.TEACHING_STRATEGY),
    ("如何改进课堂教学", TeacherIntent.TEACHING_STRATEGY),
    ("针对薄弱知识点制定策略", TeacherIntent.TEACHING_STRATEGY),
    ("你好", TeacherIntent.CASUAL_CHAT),
])
def test_read_only_intents_are_unaffected(message, expected):
    assert route_teacher_intent(message).intent == expected


# ========== 写意图词出现在只读提问里时不得误判（对抗式审查确认的回归） ==========

READ_ONLY_QUESTIONS_WITH_WRITE_WORDS = [
    "哪些作业还没发布",
    "我上周发布的作业完成情况怎么样",
    "这次作业的评分标准是什么",
    "本次作业创建到现在有多少人交了",
    "作业删除以后还能恢复吗",
    "有多少学生修改过提交内容",
    "给 90 分的标准是什么",
    "分析一下这次作业的评分分布",
    "学生提交的作业里哪些需要调整讲解重点",
]


@pytest.mark.parametrize("message", READ_ONLY_QUESTIONS_WITH_WRITE_WORDS)
def test_read_only_questions_are_never_routed_as_write(message):
    """写意图词作名词出现在提问里时，不得被判成写请求。

    误判的代价不只是走错分支：finalize 会用「未能生成草案」覆盖掉
    specialist 已经答对的内容，教师直接拿不到回答。
    """
    intent = route_teacher_intent(message).intent

    assert intent not in (
        TeacherIntent.ACTION_DRAFT,
        TeacherIntent.UNSUPPORTED_WRITE,
    )


def test_analysis_question_still_reaches_strategy_agent():
    assert route_teacher_intent(
        "分析一下这次作业的评分分布",
    ).intent == TeacherIntent.TEACHING_STRATEGY


@pytest.mark.parametrize("message", [
    "帮我发布这份作业",
    "帮我给张三的作业打 85 分",
    "删除那份还没人提交的作业",
])
def test_imperative_write_requests_still_route_to_action_draft(message):
    """疑问句豁免不能把真正的写指令一起放过。"""
    assert route_teacher_intent(message).intent == TeacherIntent.ACTION_DRAFT
