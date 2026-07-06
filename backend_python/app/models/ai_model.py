from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from ..database import Base
from .base import TimestampMixin, ModelMixin


class AiModel(Base, TimestampMixin, ModelMixin):
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    provider = Column(String(64), nullable=False)
    model_name = Column(String(128), nullable=False)
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(255), default="")
    access_key = Column(String(255), nullable=True)
    secret_key = Column(String(255), nullable=True)
    status = Column(String(20), default="inactive")
    is_default = Column(Boolean, default=False)
    total_usage = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    last_balance = Column(Float, default=0)
    balance_currency = Column(String(10), default="CNY")
    last_balance_check = Column(DateTime, nullable=True)
