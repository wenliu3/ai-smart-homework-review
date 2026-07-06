from sqlalchemy import Column, Integer, String, Text, JSON
from ..database import Base
from .base import TimestampMixin, ModelMixin


class AiRule(Base, TimestampMixin, ModelMixin):
    __tablename__ = "ai_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    model_type = Column(String(20), nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String(20), default="active")
    visibility = Column(String(20), default="private")
    tags = Column(JSON, default=list)
    max_score = Column(Integer, default=100)
    created_by = Column(JSON, nullable=True)  # {id, name}
