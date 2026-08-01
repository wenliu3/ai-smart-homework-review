"""Agent 工具包：旧工具兼容层与新结构化查询。"""
from .legacy import ALL_TOOLS, TeacherContext
from .teaching import TeachingQueryResult, query_assignment_summary, query_teacher_classes

__all__ = [
    "ALL_TOOLS",
    "TeacherContext",
    "TeachingQueryResult",
    "query_assignment_summary",
    "query_teacher_classes",
]
