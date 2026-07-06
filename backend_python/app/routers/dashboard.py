"""看板路由 — 仅做路由转发，业务逻辑在 crud/dashboard.py"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..crud import dashboard as dashboard_crud

router = APIRouter()


# ========== 管理员 ==========
@router.get("/admin/dashboard/overview")
def admin_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员看板概览 — 用户/班级/作业/提交总数 + 分布统计"""
    return ok(dashboard_crud.get_admin_overview(db))


@router.get("/admin/dashboard/ai-models")
def ai_model_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 模型使用统计 — 各模型在线状态/余额/用量"""
    return ok(dashboard_crud.get_ai_model_stats(db))


@router.get("/admin/dashboard/recent-users")
def recent_users(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取最近注册的用户列表"""
    limit = int(request.query_params.get("limit", 10))
    return ok(dashboard_crud.get_recent_users(db, limit))


@router.get("/admin/dashboard/health")
def health(current_user: User = Depends(get_current_user)):
    """系统健康检查 — 运行时长/时间戳"""
    return ok(dashboard_crud.get_health())


# ========== 教师 ==========
@router.get("/teacher/dashboard/stats")
def teacher_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师看板统计 — 班级/学生/作业/待批改/分数分析"""
    return ok(dashboard_crud.get_teacher_stats(db, current_user.id))


@router.get("/teacher/dashboard/pending-tasks")
def teacher_pending_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师待办 — 即将截止作业 + 待批改提交"""
    return ok(dashboard_crud.get_teacher_pending_tasks(db, current_user.id))


@router.get("/teacher/dashboard/performance-summary")
def teacher_performance_summary(current_user: User = Depends(get_current_user)):
    """教师绩效摘要(占位接口)"""
    return ok(dashboard_crud.get_teacher_performance_summary())


@router.get("/teacher/dashboard/quick-actions")
def teacher_quick_actions(current_user: User = Depends(get_current_user)):
    """教师快捷操作入口"""
    return ok(dashboard_crud.get_teacher_quick_actions())


# ========== 学生 ==========
@router.get("/student/dashboard/stats")
def student_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生看板统计 — 已完成/平均分/班级数/按时率/成绩分布"""
    return ok(dashboard_crud.get_student_stats(db, current_user.id))


@router.get("/student/dashboard/learning-progress")
def student_learning_progress(current_user: User = Depends(get_current_user)):
    """学生学习进度(占位接口)"""
    return ok(dashboard_crud.get_student_learning_progress())


@router.get("/student/dashboard/achievements")
def student_achievements(current_user: User = Depends(get_current_user)):
    """学生成就(占位接口)"""
    return ok(dashboard_crud.get_student_achievements())


@router.get("/student/dashboard/study-recommendations")
def student_study_recommendations(current_user: User = Depends(get_current_user)):
    """学习建议(占位接口)"""
    return ok(dashboard_crud.get_student_study_recommendations())
