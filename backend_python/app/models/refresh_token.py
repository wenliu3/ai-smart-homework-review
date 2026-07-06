from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from ..database import Base
from .base import TimestampMixin, ModelMixin


class RefreshToken(Base, TimestampMixin, ModelMixin):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
