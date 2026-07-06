from sqlalchemy import Column, Integer, String, Boolean, JSON
from ..database import Base
from .base import TimestampMixin, ModelMixin


class Role(Base, TimestampMixin, ModelMixin):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(String(255), default="")
    menu_ids = Column(JSON, default=list)
    permissions = Column(JSON, default=list)
    is_system = Column(Boolean, default=False)
    status = Column(String(20), default="active")
    remark = Column(String(255), nullable=True)
    created_by = Column(Integer, nullable=True)
