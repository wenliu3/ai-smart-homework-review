"""操作日志模型"""
from sqlalchemy import Column, Integer, String, Text
from ..database import Base
from .base import TimestampMixin, ModelMixin


class OperationLog(Base, TimestampMixin, ModelMixin):
    """操作日志 — 记录管理员/教师的关键操作"""

    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator = Column(String(64), nullable=False, comment="操作人用户名")
    operator_name = Column(String(64), nullable=True, comment="操作人姓名")
    action = Column(String(32), nullable=False, comment="操作类型: 创建/更新/删除/登录/退出/查询")
    module = Column(String(64), nullable=False, comment="操作模块: 用户管理/班级管理/作业管理...")
    description = Column(String(512), nullable=False, comment="操作描述")
    ip = Column(String(64), nullable=True, comment="IP地址")
    method = Column(String(10), nullable=True, comment="HTTP方法")
    endpoint = Column(String(255), nullable=True, comment="请求路径")
    status_code = Column(Integer, nullable=True, comment="响应状态码")
