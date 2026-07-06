"""模型基类: 时间戳混入 + 通用序列化(自动转 camelCase 并兼容 _id)"""
from datetime import datetime
from sqlalchemy import Column, DateTime, func


def snake_to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class TimestampMixin:
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ModelMixin:
    def to_dict(self, exclude=None):
        exclude = set(exclude or [])
        result = {}
        for c in self.__table__.columns:
            if c.name in exclude:
                continue
            v = getattr(self, c.name)
            if isinstance(v, datetime):
                v = v.isoformat() if v else None
            result[snake_to_camel(c.name)] = v
        # 兼容 MongoDB 风格的 _id / id（统一字符串）
        if "id" in result:
            result["_id"] = str(result["id"])
            result["id"] = str(result["id"])
        return result
