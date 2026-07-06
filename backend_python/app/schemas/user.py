"""用户相关 schemas"""
from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    name: str
    role: str = "student"
    studentId: str | None = None
    phone: str | None = None
    status: str = "active"
    mustChangePassword: bool = False


class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    status: str | None = None
    studentId: str | None = None
    phone: str | None = None
    avatar: str | None = None
    password: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    avatar: str | None = None


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class UpdateUserPasswordRequest(BaseModel):
    oldPassword: str
    newPassword: str


class ResetUserPasswordRequest(BaseModel):
    newPassword: str | None = None


class BatchDeleteRequest(BaseModel):
    userIds: list[str]
