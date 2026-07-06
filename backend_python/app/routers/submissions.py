"""提交路由 — 仅做路由转发，业务逻辑在 crud/submission.py"""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..schemas.submission import SubmitRequest, DeleteSubmissionRequest
from ..crud import submission as submission_crud

router = APIRouter()


@router.post("/students/submissions/submit")
def submit(background_tasks: BackgroundTasks, body: SubmitRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生提交作业 — 非草稿提交后异步触发 AI 批改"""
    submission = submission_crud.submit(db, current_user.id, body.model_dump())
    if not body.isDraft:
        background_tasks.add_task(submission_crud.trigger_ai_review, submission.id)
    return ok({
        "id": str(submission.id), "assignmentId": str(submission.assignment_id),
        "studentId": str(submission.student_id), "status": submission.status,
        "submittedAt": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "updatedAt": submission.updated_at.isoformat() if submission.updated_at else None,
        "isDraft": submission.is_draft, "submissionCount": submission.submission_count,
    })


@router.get("/students/submissions/my/{assignment_id}")
def get_my_submission(assignment_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生查看自己的提交详情 — 含 AI批改/教师批改结果"""
    return ok(submission_crud.get_my_submission(db, assignment_id, current_user.id))


@router.post("/students/submissions/delete")
def delete_submission(body: DeleteSubmissionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学生删除自己的草稿提交 — 只能删除 draft 状态"""
    return ok(submission_crud.delete_submission(db, body.submissionId, current_user.id))


@router.post("/teacher/submissions/delete")
def teacher_delete_submission(body: DeleteSubmissionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师删除学生提交 — 让学生可重新提交"""
    return ok(submission_crud.teacher_delete_submission(db, body.submissionId, current_user.id))
