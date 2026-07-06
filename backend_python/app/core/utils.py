"""通用工具函数"""
import re
from datetime import datetime, timezone


def now():
    """当前 UTC 时间(naive，用于写入 MySQL DateTime 列)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
