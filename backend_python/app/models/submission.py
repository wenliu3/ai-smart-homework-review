from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, JSON, ForeignKey
from ..database import Base
from .base import TimestampMixin, ModelMixin


class Submission(Base, TimestampMixin, ModelMixin):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    attachments = Column(JSON, default=list)
    content = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    status = Column(String(30), default="draft")
    submitted_at = Column(DateTime, nullable=True)
    ai_score = Column(Float, nullable=True)
    ai_review_content = Column(Text, nullable=True)
    teacher_score = Column(Float, nullable=True)
    teacher_review_content = Column(Text, nullable=True)
    teacher_reviewed_at = Column(DateTime, nullable=True)
    is_draft = Column(Boolean, default=False)
    submission_count = Column(Integer, default=1)
