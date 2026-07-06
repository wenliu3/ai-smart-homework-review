from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from ..database import Base
from .base import TimestampMixin, ModelMixin


class ClassStudent(Base, TimestampMixin, ModelMixin):
    __tablename__ = "class_students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    join_method = Column(String(20), default="code")
    status = Column(String(20), default="active")
    joined_at = Column(DateTime)
    total_submissions = Column(Integer, default=0)
    last_submission_time = Column(DateTime, nullable=True)
