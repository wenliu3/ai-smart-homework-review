"""批改路由 — 仅做路由转发，业务逻辑在 crud/correcting.py"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..schemas.submission import TeacherReviewRequest
from ..crud import correcting as correcting_crud

router = APIRouter()


@router.get("/teachers/submissions/list")
def get_submission_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师端分页查询提交列表 — 支持按作业/班级/状态过滤"""
    return ok(correcting_crud.get_submission_list(db, dict(request.query_params)))


@router.get("/teachers/submissions/detail/{submission_id}")
def get_submission_detail(submission_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取单个提交详情 — 含学生信息、附件列表"""
    return ok(correcting_crud.get_submission_detail(db, submission_id))


@router.post("/teachers/submissions/review")
def submit_teacher_review(body: TeacherReviewRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师提交批改 — 写入得分和评语，状态置 teacher_reviewed"""
    return ok(correcting_crud.submit_teacher_review(db, body.submissionId, body.teacherScore, body.teacherReviewContent))
