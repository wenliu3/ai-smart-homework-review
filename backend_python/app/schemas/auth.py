"""认证相关 schemas"""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    usernameOrEmailOrStudentId: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    confirmPassword: str
    email: str
    name: str | None = None


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str
    confirmPassword: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


# 兼容旧版 API
class LegacyLoginRequest(BaseModel):
    email: str
    password: str


class LegacyRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
