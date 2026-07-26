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
    deleted_at = Column(DateTime, nullable=True, index=True)  # 软删时间；非空即视为已删除

    @classmethod
    def alive(cls):
        """软删过滤条件。

        不变式：软删作业对所有读路径与硬删等价不可见，因此**每个**
        读取 Assignment 的查询都必须带上该条件（含 join 与 count）。
        提交记录不级联删除，便于误删后恢复。
        """
        return cls.deleted_at.is_(None)
