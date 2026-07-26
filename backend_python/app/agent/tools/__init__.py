"""Agent 工具包：旧工具兼容层与新结构化查询。"""
from .common import ALL_TOOLS, TeacherContext
from .teacher import STRUCTURED_TOOLS
from .teacher import (
    TeachingQueryResult,
    query_assignment_summary,
    query_class_students,
    query_pending_reviews,
    query_student_info,
    query_teacher_assignments,
    query_teacher_classes,
    query_teacher_dashboard,
)
from .content import (
    build_grading_input,
    build_grading_message_content,
    normalize_submission_content,
)
from .approval import create_action_draft
from .student import STUDENT_TOOLS, StudentContext
from .admin import ADMIN_TOOLS, AdminContext

__all__ = [
    "ALL_TOOLS",
    "STRUCTURED_TOOLS",
    "TeacherContext",
    "TeachingQueryResult",
    "query_assignment_summary",
    "query_class_students",
    "query_pending_reviews",
    "query_student_info",
    "query_teacher_assignments",
    "query_teacher_classes",
    "query_teacher_dashboard",
    "build_grading_input",
    "build_grading_message_content",
    "normalize_submission_content",
    "create_action_draft",
    "STUDENT_TOOLS",
    "StudentContext",
    "ADMIN_TOOLS",
    "AdminContext",
]
