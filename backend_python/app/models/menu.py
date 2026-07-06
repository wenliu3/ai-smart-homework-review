from sqlalchemy import Column, Integer, String, Boolean, JSON
from ..database import Base
from .base import TimestampMixin, ModelMixin


class Menu(Base, TimestampMixin, ModelMixin):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    path = Column(String(255), nullable=False)
    component = Column(String(255), nullable=True)
    redirect = Column(String(255), nullable=True)
    type = Column(String(20), nullable=False)  # menu | button
    parent_id = Column(Integer, nullable=True, index=True)
    icon = Column(String(64), nullable=True)
    sort = Column(Integer, default=0)
    hidden = Column(Boolean, default=False)
    status = Column(String(20), default="active")
    meta = Column(JSON, nullable=True)
    is_system = Column(Boolean, default=False)
    created_by = Column(JSON, nullable=True)
