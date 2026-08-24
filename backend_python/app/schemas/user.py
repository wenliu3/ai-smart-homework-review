"""用户相关 schemas — 服务端参数校验（不能只依赖前端表单校验）"""
import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

UserRole = Literal["student", "teacher", "superadmin"]
UserStatus = Literal["active", "inactive", "locked"]

# 与前端校验规则保持一致的邮箱/手机号格式
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=20)
    email: str = Field(..., max_length=128)
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1, max_length=64)
    role: UserRole = "student"
    studentId: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=32)
    status: UserStatus = "active"
    mustChangePassword: bool = False

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        if not EMAIL_PATTERN.match(v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        if v and not PHONE_PATTERN.match(v):
            raise ValueError("手机号格式不正确")
        return v or None

    @field_validator("username", "name")
    @classmethod
    def _strip_required(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("不能为空白字符")
        return v

    @field_validator("studentId")
    @classmethod
    def _strip_student_id(cls, v: str | None) -> str | None:
        return v.strip() or None if v else v

    @model_validator(mode="after")
    def _check_student_fields(self) -> "UserCreate":
        if self.role == "student" and not self.studentId:
            raise ValueError("学生角色必须填写学号")
        return self


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    email: str | None = Field(None, max_length=128)
    role: UserRole | None = None
    status: UserStatus | None = None
    studentId: str | None = Field(None, max_length=64)
    phone: str | None = Field(None, max_length=32)
    avatar: str | None = Field(None, max_length=512)
    password: str | None = Field(None, min_length=6)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str | None) -> str | None:
        if v and not EMAIL_PATTERN.match(v):
            raise ValueError("邮箱格式不正确")
        return v

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        if v and not PHONE_PATTERN.match(v):
            raise ValueError("手机号格式不正确")
        return v or None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("不能为空白字符")
        return v

    @field_validator("studentId")
    @classmethod
    def _strip_student_id(cls, v: str | None) -> str | None:
        # 显式传空字符串视为清除学号（角色改为非学生时前端会传空）
        return v.strip() or None if v else v


class ResetUserPasswordRequest(BaseModel):
    newPassword: str | None = Field(None, min_length=6)


class BatchDeleteRequest(BaseModel):
    userIds: list[str]
