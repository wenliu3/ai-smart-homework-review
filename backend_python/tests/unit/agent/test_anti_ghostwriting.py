"""防代写加固（规划阶段 5.2）。

- 学生请求与进行中作业题面相似度过高 → 升级为 PROHIBITED_ANSWER。
- 概念讲解（LEARNING_COACH）豁免「本人数据证据」硬门槛（LLM 审核仍在）。
- 输出完整度约束：辅导类回答过长疑似完整代写 → 确定性拒绝。
"""
from datetime import datetime, timedelta

import pytest

from app.agent.contracts import ReviewResult, StudentIntent, StudentIntentDecision
from app.agent.subagents import student_final_reviewer
from app.agent.supervisors.student import StudentSupervisor
from app.agent.tools.student import (
    build_topic_similarity_checker,
    message_matches_topics,
)
from app.models import Assignment, Class, ClassStudent

TOPIC = "论述光合作用的基本过程，并结合实验说明影响光合速率的三个因素"


# ========== 相似度判定（纯函数） ==========

def test_verbatim_topic_paste_is_flagged():
    assert message_matches_topics(
        f"帮我写：{TOPIC}", [TOPIC],
    ) is True


def test_partial_topic_overlap_is_flagged():
    assert message_matches_topics(
        "论述光合作用的基本过程，并结合实验说明影响因素", [TOPIC],
    ) is True


def test_unrelated_question_is_not_flagged():
    assert message_matches_topics(
        "什么是二叉树的中序遍历", [TOPIC],
    ) is False


def test_short_or_empty_inputs_never_flag():
    assert message_matches_topics("光合作用", [TOPIC]) is False
    assert message_matches_topics("", [TOPIC]) is False
    assert message_matches_topics("随便聊聊", []) is False


# ========== 主管升级拦截 ==========

def test_topic_similarity_escalates_to_prohibited():
    supervisor = StudentSupervisor(
        topic_similarity_checker=lambda message, student_id: True,
    )

    update = supervisor.route({"user_message": f"帮我解答一下：{TOPIC}"})

    decision = update["intent"]
    assert decision.intent == StudentIntent.PROHIBITED_ANSWER
    assert "题面" in decision.reason


def test_topic_checker_failure_keeps_normal_route():
    def broken(message, student_id):
        raise RuntimeError("db down")

    supervisor = StudentSupervisor(topic_similarity_checker=broken)

    update = supervisor.route({"user_message": "怎么做这道推导题，给点思路"})

    assert update["intent"].intent == StudentIntent.LEARNING_COACH


def test_casual_chat_skips_topic_check():
    calls = []
    supervisor = StudentSupervisor(
        topic_similarity_checker=lambda m, s: calls.append(m) or True,
    )

    update = supervisor.route({"user_message": "你好"})

    assert update["intent"].intent == StudentIntent.CASUAL_CHAT
    assert calls == []


# ========== 数据侧题面查询（服务端专用，不注册为 LLM 工具） ==========

def test_checker_reads_active_assignment_topics(db, teacher, student):
    klass = Class(name="防代写班", code="AGW1", teacher_id=teacher.id)
    db.add(klass)
    db.commit()
    db.add(ClassStudent(
        class_id=klass.id, student_id=student.id, status="active",
    ))
    assignment = Assignment(
        title="生物作业",
        description=TOPIC,
        teacher_id=teacher.id,
        teacher_name=teacher.name,
        classes=[{"id": str(klass.id), "name": klass.name}],
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now() + timedelta(days=7),
        status="published",
    )
    db.add(assignment)
    db.commit()

    checker = build_topic_similarity_checker()

    assert checker(f"帮我写一下：{TOPIC}", student.id) is True
    assert checker("什么是二叉树的中序遍历", student.id) is False


def test_llm_tool_list_never_exposes_topic_query():
    """题面查询绝不注册为 LLM 工具——否则等于把题面递给代写请求。"""
    from app.agent.tools.student import STUDENT_TOOLS

    names = {tool.name for tool in STUDENT_TOOLS}
    assert not any("topic" in name for name in names)


# ========== 审核：概念讲解豁免与完整度约束 ==========

class _ApprovingAgent:
    def invoke(self, payload):
        return {"structured_response": {"approved": True, "issues": []}}


class _Registry:
    def get_specialist(self, name, db):
        return _ApprovingAgent()


def _review(intent, candidate, evidence=None):
    node = student_final_reviewer.create_node(object(), _Registry())
    return node({
        "candidate_answer": candidate,
        "evidence_refs": evidence or [],
        "intent": StudentIntentDecision(
            intent=intent, target_agent="x",
        ),
    })["review"]


def test_learning_coach_without_evidence_is_now_allowed():
    review = _review(StudentIntent.LEARNING_COACH, "先想想反应物是什么？")

    assert review.approved is True


def test_feedback_explanation_still_requires_evidence():
    review = _review(StudentIntent.FEEDBACK_EXPLANATION, "你的扣分点在……")

    assert review.approved is False
    assert any("证据" in issue for issue in review.issues)


def test_oversized_coach_answer_is_rejected_deterministically():
    essay = "光合作用的完整论述。" * 200  # 远超完整度阈值

    review = _review(StudentIntent.LEARNING_COACH, essay)

    assert review.approved is False
    assert any("过长" in issue or "完整" in issue for issue in review.issues)
