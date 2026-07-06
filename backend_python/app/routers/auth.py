"""认证路由 — 仅做路由转发，业务逻辑在 crud/auth.py"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..core.exceptions import BadRequestException
from ..schemas.auth import (
    LoginRequest, RegisterRequest, RefreshTokenRequest,
    ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest,
    LegacyLoginRequest, LegacyRegisterRequest,
)
from ..crud import auth as auth_crud

router = APIRouter()


@router.post("/v1/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """用户登录 — 支持用户名/邮箱/学号登录，返回 JWT + RefreshToken"""
    return ok(auth_crud.login(db, body.usernameOrEmailOrStudentId, body.password))


@router.post("/v1/auth/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """退出登录 — 撤销当前用户所有 RefreshToken"""
    return ok(auth_crud.logout(db, current_user.id))


@router.post("/v1/auth/refresh-token")
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    """刷新令牌 — 用 RefreshToken 换取新的 JWT + RefreshToken"""
    return ok(auth_crud.refresh_token(db, body.refreshToken))


@router.get("/v1/auth/profile")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前登录用户信息"""
    return ok(auth_crud.get_profile(db, current_user))


@router.put("/v1/auth/password")
def change_password(body: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """修改密码 — 需校验原密码与新密码一致性"""
    if body.newPassword != body.confirmPassword:
        raise BadRequestException(10008, "两次密码输入不一致")
    return ok(auth_crud.change_password(db, current_user, body.currentPassword, body.newPassword))


@router.put("/v1/auth/first-password-change")
def first_change_password(body: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """首次登录强制改密 — 改密后取消 mustChangePassword 标记"""
    if body.newPassword != body.confirmPassword:
        raise BadRequestException(10008, "两次密码输入不一致")
    return ok(auth_crud.first_change_password(db, current_user, body.currentPassword, body.newPassword))


@router.post("/v1/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """忘记密码 — 不暴露邮箱是否存在，实际需接入邮件服务"""
    return ok({"success": True})


@router.post("/v1/auth/reset-password")
def reset_password(body: ResetPasswordRequest):
    """重置密码 — 需配置邮件服务后实现"""
    raise BadRequestException(10010, "重置密码功能需要配置邮件服务")


@router.post("/v1/auth/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册 — 注册成功后返回 JWT"""
    if body.password != body.confirmPassword:
        raise BadRequestException(10008, "两次密码输入不一致")
    return ok(auth_crud.register(db, body.username, body.password, body.email, body.name))


# ===== 兼容旧版 API（无 v1 前缀）=====
@router.post("/auth/login")
def login_legacy(body: LegacyLoginRequest, db: Session = Depends(get_db)):
    """旧版登录 — 兼容无 v1 前缀的 API"""
    return ok(auth_crud.login(db, body.email, body.password))


@router.post("/auth/register")
def register_legacy(body: LegacyRegisterRequest, db: Session = Depends(get_db)):
    """旧版注册 — 兼容无 v1 前缀的 API"""
    return ok(auth_crud.register_legacy(db, body.email, body.name, body.password))
