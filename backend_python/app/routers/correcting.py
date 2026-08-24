"""批改路由 — 仅做路由转发，业务逻辑在 crud/correcting.py

教师角色 + 作业归属双重校验：教师只能查看/批改自己作业下的提交。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_roles
from ..models import User
from ..core.response import ok
from ..schemas.submission import TeacherReviewRequest
from ..crud import correcting as correcting_crud

router = APIRouter()


@router.get("/teachers/submissions/list")
def get_submission_list(request: Request, current_user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    """教师端分页查询提交列表 — 仅返回当前教师自己作业的提交，支持按作业/班级/状态过滤"""
    return ok(correcting_crud.get_submission_list(db, dict(request.query_params), current_user.id))


@router.get("/teachers/submissions/detail/{submission_id}")
def get_submission_detail(submission_id: int, current_user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    """获取单个提交详情 — 含学生信息、附件列表；仅限作业归属教师"""
    return ok(correcting_crud.get_submission_detail(db, submission_id, current_user.id))


@router.post("/teachers/submissions/review")
def submit_teacher_review(body: TeacherReviewRequest, current_user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    """教师提交批改 — 写入得分和评语，状态置 teacher_reviewed；仅限作业归属教师"""
    return ok(correcting_crud.submit_teacher_review(
        db, body.submissionId, body.teacherScore, body.teacherReviewContent,
        actor_user_id=current_user.id,
    ))
