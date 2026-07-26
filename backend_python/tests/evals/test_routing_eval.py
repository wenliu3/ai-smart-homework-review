from app.agent.supervisors.admin import AdminSupervisor
from app.agent.supervisors.student import StudentSupervisor
from app.agent.supervisors.teacher import TeacherSupervisor
from tests.evals.cases.catalog import ROUTING_CASES


def test_offline_routing_accuracy_is_at_least_95_percent():
    supervisors = {
        "teacher": TeacherSupervisor(),
        "student": StudentSupervisor(),
        "superadmin": AdminSupervisor(),
    }
    correct = 0
    for role, message, expected in ROUTING_CASES:
        result = supervisors[role].route({"user_message": message})
        correct += result["intent"].intent.value == expected

    assert correct / len(ROUTING_CASES) >= 0.95

def test_adversarial_routing_with_llm_fallback_hits_95_percent():
    """对抗样本关键词全 miss；用「答对的分类器桩」模拟 LLM 验证兜底接线。

    桩只在主管把消息交给分类器时才有机会生效——若接线断了
    （关键词命中路径误调、默认分支未调用），准确率会跌破门槛。
    """
    from tests.evals.cases.catalog import ADVERSARIAL_ROUTING_CASES

    def make_supervisor(role, expected):
        classifier = lambda message: expected
        if role == "teacher":
            return TeacherSupervisor(route_classifier=classifier)
        if role == "student":
            return StudentSupervisor(route_classifier=classifier)
        return AdminSupervisor(route_classifier=classifier)

    correct = 0
    for role, message, expected in ADVERSARIAL_ROUTING_CASES:
        supervisor = make_supervisor(role, expected)
        result = supervisor.route({"user_message": message})
        correct += result["intent"].intent.value == expected

    assert correct / len(ADVERSARIAL_ROUTING_CASES) >= 0.95


def test_adversarial_cases_actually_miss_keywords():
    """守护：对抗样本必须真的绕开关键词表，否则测的不是兜底。"""
    from tests.evals.cases.catalog import ADVERSARIAL_ROUTING_CASES

    supervisors = {
        "teacher": TeacherSupervisor(),
        "student": StudentSupervisor(),
        "superadmin": AdminSupervisor(),
    }
    defaults = {
        "teacher": "teaching_data",
        "student": "learning_coach",
        "superadmin": "operations_analysis",
    }
    for role, message, expected in ADVERSARIAL_ROUTING_CASES:
        result = supervisors[role].route({"user_message": message})
        routed = result["intent"].intent.value
        # 纯关键词下要么落默认分支，要么恰好等于期望（禁止落到其它意图）
        assert routed in (defaults[role], expected), (role, message, routed)
