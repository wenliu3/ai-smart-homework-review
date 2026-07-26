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
