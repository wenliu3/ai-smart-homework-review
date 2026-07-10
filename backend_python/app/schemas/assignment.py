"""作业相关 schemas"""
from datetime import datetime
from pydantic import BaseModel


class AssignmentCreate(BaseModel):
    title: str
    description: str = ""
    classes: list[str]
    startDate: datetime
    endDate: datetime
    aiRule: dict | None = None
    attachments: list[dict] = []  # 教师上传的作业附件
    allowAttachments: bool = False


class AssignmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    classes: list[str] | None = None
    startDate: datetime | None = None
    endDate: datetime | None = None
    aiRule: dict | None = None
    attachments: list[dict] | None = None
    allowAttachments: bool | None = None


class UpdateStatusRequest(BaseModel):
    status: str
    terminatedReason: str | None = None
