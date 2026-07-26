"""LLM 路由兜底（规划阶段 5.1）。

- 关键词命中时绝不调用 LLM 分类器（成本与确定性优先）。
- 关键词未命中（落默认分支）时调用分类器至多一次。
- 分类器返回非法标签/抛异常时回退关键词默认值。
- 高风险意图（写操作/代写拦截）不受分类器影响——安全路由不许被 LLM 改写。
"""
import pytest

from app.agent.contracts import AdminIntent, StudentIntent, TeacherIntent
from app.agent.supervisors.admin import AdminSupervisor
from app.agent.supervisors.llm_router import (
    ROLE_ROUTE_LABELS,
    parse_route_label,
)
from app.agent.supervisors.student import StudentSupervisor
from app.agent.supervisors.teacher import TeacherSupervisor


class _Recorder:
    def __init__(self, label):
        self.label = label
        self.calls = []

    def __call__(self, message: str):
        self.calls.append(message)
        return self.label


# ========== 标签解析 ==========

def test_role_labels_cover_all_routable_intents():
    # 写意图（action_draft）不给 LLM：写路径只能由确定性关键词开启
    assert ROLE_ROUTE_LABELS["teacher"] == {
        "casual_chat", "teaching_data", "teaching_strategy",
    }
    # prohibited_answer 保留给 LLM：改写代写请求被兜底拦截是安全增强
    assert "prohibited_answer" in ROLE_ROUTE_LABELS["student"]
    assert set(ROLE_ROUTE_LABELS) == {"teacher", "student", "superadmin"}


@pytest.mark.parametrize("raw,expected", [
    ("teaching_strategy", "teaching_strategy"),
    ("  Teaching_Strategy \n", "teaching_strategy"),
    ('"teaching_data"', "teaching_data"),
    ("unknown_label", None),
    ("", None),
    (None, None),
])
def test_parse_route_label_is_strict(raw, expected):
    assert parse_route_label(raw, role="teacher") == expected


# ========== 教师主管 ==========

def test_keyword_hit_never_calls_classifier():
    classifier = _Recorder("teaching_data")
    supervisor = TeacherSupervisor(route_classifier=classifier)

    supervisor.route({"user_message": "分析最近成绩趋势"})
    supervisor.route({"user_message": "帮我发布这份作业"})
    supervisor.route({"user_message": "你好"})

    assert classifier.calls == []


def test_keyword_miss_consults_classifier_once():
    classifier = _Recorder("teaching_strategy")
    supervisor = TeacherSupervisor(route_classifier=classifier)

    update = supervisor.route({"user_message": "期中之后班里状态有点散"})

    assert classifier.calls == ["期中之后班里状态有点散"]
    decision = update["intent"]
    assert decision.intent == TeacherIntent.TEACHING_STRATEGY
    assert "llm" in decision.reason.lower()


def test_invalid_label_falls_back_to_keyword_default():
    supervisor = TeacherSupervisor(route_classifier=_Recorder("nonsense"))

    update = supervisor.route({"user_message": "期中之后班里状态有点散"})

    assert update["intent"].intent == TeacherIntent.TEACHING_DATA


def test_classifier_exception_falls_back_to_keyword_default():
    def broken(message):
        raise RuntimeError("model unavailable")

    supervisor = TeacherSupervisor(route_classifier=broken)

    update = supervisor.route({"user_message": "期中之后班里状态有点散"})

    assert update["intent"].intent == TeacherIntent.TEACHING_DATA


def test_classifier_cannot_rewrite_into_write_intent():
    """分类器给出 action_draft 也只能落到低风险读意图之外的……写意图必须走关键词安全路由。"""
    supervisor = TeacherSupervisor(route_classifier=_Recorder("action_draft"))

    update = supervisor.route({"user_message": "期中之后班里状态有点散"})

    # LLM 不得开启写路径：action_draft 标签被拒，回退默认
    assert update["intent"].intent == TeacherIntent.TEACHING_DATA


# ========== 学生主管 ==========

def test_student_prohibited_route_ignores_classifier():
    classifier = _Recorder("learning_coach")
    supervisor = StudentSupervisor(route_classifier=classifier)

    update = supervisor.route({"user_message": "替我写完这篇作文可以提交的"})

    assert update["intent"].intent == StudentIntent.PROHIBITED_ANSWER
    assert classifier.calls == []


def test_student_default_branch_uses_classifier():
    supervisor = StudentSupervisor(
        route_classifier=_Recorder("feedback_explanation"),
    )

    update = supervisor.route({"user_message": "老师给的分数我有点看不懂"})

    assert update["intent"].intent == StudentIntent.FEEDBACK_EXPLANATION


# ========== 管理员主管 ==========

def test_admin_default_branch_uses_classifier():
    supervisor = AdminSupervisor(route_classifier=_Recorder("audit_analysis"))

    update = supervisor.route({"user_message": "最近平台有没有什么不对劲的地方"})

    assert update["intent"].intent == AdminIntent.AUDIT_ANALYSIS


def test_admin_classifier_cannot_grant_approval_flag():
    """LLM 兜底产生的模型治理意图不带 requires_approval（写路径仍靠关键词）。"""
    supervisor = AdminSupervisor(route_classifier=_Recorder("model_governance"))

    update = supervisor.route({"user_message": "帮我瞧瞧智能服务最近跑得稳不稳"})

    decision = update["intent"]
    assert decision.intent == AdminIntent.MODEL_GOVERNANCE
    assert decision.requires_approval is False
