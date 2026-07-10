from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, ForeignKey
from ..database import Base
from .base import TimestampMixin, ModelMixin


class Assignment(Base, TimestampMixin, ModelMixin):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    teacher_name = Column(String(64), nullable=False)
    classes = Column(JSON, default=list)  # [{id, name}, ...]
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="draft")
    terminated_reason = Column(String(255), nullable=True)
    ai_rule = Column(JSON, nullable=True)
    attachments = Column(JSON, default=list)  # 教师上传的作业附件 [{fileName, fileUrl, fileSize, fileType}]
    allow_attachments = Column(Boolean, default=False)  # 是否允许学生上传附件
