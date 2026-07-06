from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from ..database import Base
from .base import TimestampMixin, ModelMixin


class User(Base, TimestampMixin, ModelMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    name = Column(String(64), nullable=False)
    role = Column(String(20), nullable=False, default="student")
    status = Column(String(20), nullable=False, default="active")
    student_id = Column(String(64), nullable=True, index=True)
    phone = Column(String(32), nullable=True)
    avatar = Column(String(512), nullable=True)
    meta = Column(JSON, nullable=True)
    must_change_password = Column(Boolean, default=False)
    first_login_at = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    role_ids = Column(JSON, default=list)
