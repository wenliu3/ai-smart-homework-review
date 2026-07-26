"""Agent 公共上下文与旧助手兼容工具适配层。

每个 @tool 函数只做薄包装：从 runtime.context 取出 TeacherContext，
调用同名 format_xxx 函数。format_xxx 负责调用结构化查询并格式化为
LLM 可读的字符串。

teacher_id 仅从 TeacherContext 取得，绝不作为 LLM 工具参数暴露。
每个 format_xxx 内部用 SessionLocal() 创建独立 MySQL Session，保证
LangGraph 后台线程安全（pymysql 连接非线程安全）。
"""
import functools
from dataclasses import dataclass

from langchain.tools import ToolRuntime, tool

from ...database import SessionLocal
from ..runtime import RunBudget


@dataclass
class TeacherContext:
    """每次 agent.invoke()/stream() 时传入，工具通过 runtime.context 访问。
    teacher_id 不出现在任何工具的参数里，LLM 既看不到也填不了这个值，
    从根源上避免"模型自己决定查哪个老师的数据"这种越权风险。

    注意：不传 db session。因为 langgraph 在后台线程里执行工具，
    共享请求线程的 session 会导致 pymysql "Packet sequence number wrong" 错误
    （pymysql 连接不是线程安全的）。每个工具内部用 SessionLocal() 创建独立
    session（独立连接），保证线程安全。"""
    teacher_id: int
    budget: RunBudget | None = None


def _teacher_queries():
    """延迟加载教师查询，避免 common 与 teacher 的模块初始化循环。"""
    from . import teacher

    return teacher


def _safe_tool(fn):
    """工具异常友好降级：DB 抖动等异常时返回友好提示，
    避免 traceback 经 ToolMessage 泄露给 LLM 导致奇怪回答。"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return "查询暂时失败，请稍后再试。"
    return wrapper


# ========== 格式化函数（可直接测试，不依赖 LangChain 工具调用机制）==========

def format_teacher_classes(ctx: TeacherContext) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_teacher_classes(db, actor_id=ctx.teacher_id)
    if result.status == "empty":
        return "您目前没有任何班级。"
    lines = [
        f"- {r['name']}（学生:{r['studentCount']}，状态:{r['status']}）"
        for r in result.records
    ]
    return f"您共有 {result.metrics['classCount']} 个班级：\n" + "\n".join(lines)


def format_class_students(ctx: TeacherContext, class_id: int) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_class_students(
            db,
            actor_id=ctx.teacher_id,
            class_id=class_id,
        )
    if result.status == "not_found":
        return f"未找到班级ID {class_id}，或该班级不属于您。"
    if result.status == "empty":
        return f"班级「{result.title.replace(' 学生列表', '')}」中暂无活跃学生。"
    lines = [
        f"- {r['name']}（学号:{r.get('studentId') or '无'}，状态:{r.get('status', '未知')}）"
        for r in result.records
    ]
    return f"{result.title}共 {result.metrics['studentCount']} 名学生：\n" + "\n".join(lines)


def format_teacher_assignments(ctx: TeacherContext) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_teacher_assignments(db, actor_id=ctx.teacher_id)
    if result.status == "empty":
        return "您目前还没有创建任何作业。"
    lines = [
        f"- 「{r['title']}」（状态:{r['status']}，截止:{r.get('endDate') or '无'}）"
        for r in result.records
    ]
    return f"您共有 {result.metrics['assignmentCount']} 个作业：\n" + "\n".join(lines)


def format_assignment_submissions(ctx: TeacherContext, assignment_id: int) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_assignment_summary(
            db,
            actor_id=ctx.teacher_id,
            assignment_id=assignment_id,
        )
    if result.status == "not_found":
        return f"未找到作业ID {assignment_id}，或该作业不属于您。"
    m = result.metrics
    return (
        f"作业「{result.title}」提交情况：\n"
        f"  总提交:{m.get('submissionCount', 0)}，"
        f"待批改:{m.get('pendingCount', 0)}，"
        f"AI已评:{m.get('aiReviewedCount', 0)}，"
        f"教师已评:{m.get('teacherReviewedCount', 0)}"
    )


def format_student_info(ctx: TeacherContext, student_name_or_id: str) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_student_info(
            db,
            actor_id=ctx.teacher_id,
            student_name_or_id=student_name_or_id,
        )
    if result.status in ("not_found", "empty"):
        return f"未找到匹配「{student_name_or_id}」的学生，或该学生不在您的班级中。"
    lines = []
    for r in result.records:
        lines.append(
            f"- 姓名:{r['name']}，学号:{r.get('studentId') or '无'}，状态:{r.get('status', '未知')}"
        )
    return f"匹配到 {result.metrics['studentCount']} 名学生：\n" + "\n".join(lines)


def format_teacher_dashboard_stats(ctx: TeacherContext) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_teacher_dashboard(db, actor_id=ctx.teacher_id)
    m = result.metrics
    if result.status == "empty":
        return (
            "教学概况：\n"
            f"  班级数:{m.get('classCount', 0)}\n"
            f"  作业总数:{m.get('assignmentCount', 0)}\n"
            f"  提交总数:0\n"
            f"  待批改:0"
        )
    return (
        "教学概况：\n"
        f"  班级数:{m.get('classCount', 0)}\n"
        f"  作业总数:{m.get('assignmentCount', 0)}\n"
        f"  提交总数:{m.get('submissionCount', 0)}\n"
        f"  待批改:{m.get('pendingCount', 0)}"
    )


def format_pending_reviews(ctx: TeacherContext) -> str:
    with SessionLocal() as db:
        result = _teacher_queries().query_pending_reviews(db, actor_id=ctx.teacher_id)
    if result.status == "empty":
        return "当前没有待批改的提交。"
    lines = [
        f"- {r['assignmentTitle']}（学生ID:{r['studentId']}，提交时间:{r.get('submittedAt') or '未知'}）"
        for r in result.records
    ]
    return f"待批改提交（共 {result.metrics['pendingCount']} 条）：\n" + "\n".join(lines)


# ========== LangChain 工具（薄包装，保留原工具名和 TeacherContext）==========

@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_teacher_classes(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询当前教师的所有班级列表，包含班级名称、学生人数、状态；当教师询问"我有几个班级"或"班级情况"时使用。"""
    return format_teacher_classes(runtime.context)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_class_students(class_id: int, runtime: ToolRuntime[TeacherContext]) -> str:
    """查询指定班级的学生列表，包含姓名、学号、状态；只能查询当前教师自己名下的班级，当教师询问"某班有哪些学生"时使用。

    Args:
        class_id: 班级ID(整数)
    """
    return format_class_students(runtime.context, class_id=class_id)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_teacher_assignments(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询当前教师的所有作业列表，包含标题、状态、截止时间；当教师询问"我的作业"或"发布了几个作业"时使用。"""
    return format_teacher_assignments(runtime.context)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_assignment_submissions(assignment_id: int, runtime: ToolRuntime[TeacherContext]) -> str:
    """查询某作业下所有学生的提交情况，包含提交状态、AI分数、教师分数；只能查询当前教师自己创建的作业，当教师询问"这个作业交了多少人"或"批改进度"时使用。

    Args:
        assignment_id: 作业ID(整数)
    """
    return format_assignment_submissions(runtime.context, assignment_id=assignment_id)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_student_info(student_name_or_id: str, runtime: ToolRuntime[TeacherContext]) -> str:
    """按姓名或学号查询学生信息及其提交记录；只能查询当前教师所带班级中的学生，当教师询问"某学生的信息"或"某某的成绩"时使用。

    Args:
        student_name_or_id: 学生姓名或学号，支持模糊匹配
    """
    return format_student_info(runtime.context, student_name_or_id=student_name_or_id)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_teacher_dashboard_stats(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询教师看板统计数据，包含班级数、学生数、作业数、待批改数等；当教师询问"我的教学概况"或"整体数据"时使用。"""
    return format_teacher_dashboard_stats(runtime.context)


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_pending_reviews(runtime: ToolRuntime[TeacherContext]) -> str:
    """查询当前教师的待批改提交列表；当教师询问"有哪些待批改"或"还没改的作业"时使用。"""
    return format_pending_reviews(runtime.context)


# 工具列表在模块加载时就固定下来 — 供 Agent 使用，不用每次请求重建
ALL_TOOLS = [
    get_teacher_classes,
    get_class_students,
    get_teacher_assignments,
    get_assignment_submissions,
    get_student_info,
    get_teacher_dashboard_stats,
    get_pending_reviews,
]
