"""提交相关 schemas"""
from pydantic import BaseModel


class AttachmentItem(BaseModel):
    fileName: str
    fileUrl: str
    fileSize: int
    fileType: str


class SubmitRequest(BaseModel):
    assignmentId: int
    classId: int
    content: str = ""
    attachments: list[dict] = []
    isDraft: bool = False


class DeleteSubmissionRequest(BaseModel):
    submissionId: int


class TeacherReviewRequest(BaseModel):
    submissionId: int
    teacherReviewContent: str
    teacherScore: float
