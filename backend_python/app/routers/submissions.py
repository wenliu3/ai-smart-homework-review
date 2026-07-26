"""提交路由 — 仅做路由转发，业务逻辑在 CRUD/Task Service。"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..assistant_database import get_assistant_db
from ..database import get_db
from ..deps import require_roles
from ..models import User
from ..core.response import ok
from ..schemas.submission import SubmitRequest, DeleteSubmissionRequest
from ..crud import submission as submission_crud
from ..tasks.grading import enqueue_grading_job

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/students/submissions/submit")
def submit(
    body: SubmitRequest,
    current_user: User = Depends(require_roles("student")),
    db: Session = Depends(get_db),
    assistant_db: Session = Depends(get_assistant_db),
):
    """学生提交作业 — 非草稿提交后投递持久化 AI 批改任务。"""
    submission = submission_crud.submit(db, current_user.id, body.model_dump())
    grading_run_id = None
    grading_scheduling_status = "not_requested"
    if not body.isDraft:
        try:
            grading_run_id = enqueue_grading_job(
                db,
                assistant_db,
                submission=submission,
                user_id=current_user.id,
                actor_role=current_user.role,
            )
            grading_scheduling_status = (
                "scheduled" if grading_run_id else "not_configured"
            )
        except Exception:
            assistant_db.rollback()
            grading_scheduling_status = "failed"
            logger.exception(
                "作业已提交，但 AI 批改任务投递失败: submission_id=%s",
                submission.id,
            )
    return ok({
        "id": str(submission.id), "assignmentId": str(submission.assignment_id),
        "studentId": str(submission.student_id), "status": submission.status,
        "submittedAt": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "updatedAt": submission.updated_at.isoformat() if submission.updated_at else None,
        "isDraft": submission.is_draft, "submissionCount": submission.submission_count,
        "gradingRunId": grading_run_id,
        "gradingSchedulingStatus": grading_scheduling_status,
    })


@router.get("/students/submissions/my/{assignment_id}")
def get_my_submission(assignment_id: int, current_user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """学生查看自己的提交详情 — 含 AI批改/教师批改结果"""
    return ok(submission_crud.get_my_submission(db, assignment_id, current_user.id))


@router.post("/students/submissions/delete")
def delete_submission(body: DeleteSubmissionRequest, current_user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    """学生删除自己的草稿提交 — 只能删除 draft 状态"""
    return ok(submission_crud.delete_submission(db, body.submissionId, current_user.id))


@router.post("/teacher/submissions/delete")
def teacher_delete_submission(body: DeleteSubmissionRequest, current_user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    """教师删除学生提交 — 让学生可重新提交"""
    return ok(submission_crud.teacher_delete_submission(db, body.submissionId, current_user.id))
