"""作业路由 — 仅做路由转发，业务逻辑在 crud/assignment.py"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..schemas.assignment import AssignmentCreate, AssignmentUpdate, UpdateStatusRequest
from ..crud import assignment as assignment_crud

router = APIRouter()


# ========== 教师端 ==========
@router.get("/teacher/assignments")
def get_teacher_assignments(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师端分页查询自己的作业列表 — 含提交/批改统计"""
    return ok(assignment_crud.get_teacher_assignments(db, current_user.id, dict(request.query_params)))


@router.get("/teacher/assignments/{assignment_id}")
def get_teacher_detail(assignment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取单个作业详情 — 含提交统计"""
    return ok(assignment_crud.get_teacher_detail(db, assignment_id))


@router.get("/teacher/assignments/{assignment_id}/students")
def get_assignment_students(assignment_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询某作业下的学生提交列表 — 含学生姓名/得分"""
    return ok(assignment_crud.get_assignment_students(db, assignment_id, dict(request.query_params)))


@router.post("/teacher/assignments")
def create_assignment(body: AssignmentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建作业 — 关联班级，状态默认 draft"""
    return ok(assignment_crud.create_assignment(db, current_user.id, current_user.name, body.model_dump()))


@router.post("/teacher/assignments/{assignment_id}/update")
def update_assignment(assignment_id: int, body: AssignmentUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新作业 — 仅作业创建教师可操作"""
    return ok(assignment_crud.update_assignment(db, assignment_id, current_user.id, body.model_dump(exclude_unset=True)))


@router.post("/teacher/assignments/{assignment_id}/status")
def update_status(assignment_id: int, body: UpdateStatusRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新作业状态(draft/published/terminated)"""
    return ok(assignment_crud.update_status(db, assignment_id, current_user.id, body.status, body.terminatedReason))


@router.post("/teacher/assignments/{assignment_id}/delete")
def delete_assignment(assignment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除作业 — 同时删除关联的提交记录"""
    return ok(assignment_crud.delete_assignment(db, assignment_id, current_user.id))


# ========== 作业查重 ==========
@router.post("/teacher/assignments/{assignment_id}/plagiarism")
def check_plagiarism(assignment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """作业查重 — 对该作业所有学生提交进行两两比对，返回重复率排名"""
    return ok(assignment_crud.check_plagiarism(db, assignment_id, current_user.id))


# ========== 学生端 ==========
@router.get("/student/assignments")
def get_student_assignments(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生查询已发布的作业列表 — 含每个作业的提交状态"""
    return ok(assignment_crud.get_student_assignments(
        db, current_user.id,
        request.query_params.get("classId"),
        request.query_params.get("businessStatus"),
    ))


@router.get("/student/assignments/statistics")
def get_student_statistics(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生作业统计 — 总数/已提交/已批改/待办/草稿/过期"""
    return ok(assignment_crud.get_student_statistics(db, current_user.id, request.query_params.get("classId")))


@router.get("/student/assignments/{assignment_id}")
def get_student_detail(assignment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生查看作业详情 — 含自己的提交记录"""
    return ok(assignment_crud.get_student_detail(db, assignment_id, current_user.id))
