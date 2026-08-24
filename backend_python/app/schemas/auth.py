"""认证相关 schemas"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    usernameOrEmailOrStudentId: str
    password: str


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str
    confirmPassword: str
