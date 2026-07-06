from sqlalchemy import Column, Integer, String, ForeignKey
from ..database import Base
from .base import TimestampMixin, ModelMixin


class Class(Base, TimestampMixin, ModelMixin):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    code = Column(String(32), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(String(512), default="")
    status = Column(String(20), default="active")
    max_students = Column(Integer, default=200)
    student_count = Column(Integer, default=0)
