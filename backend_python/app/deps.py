"""FastAPI 依赖注入: 当前用户、角色校验"""
from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .core.security import decode_access_token
from .core.exceptions import UnauthorizedException, ForbiddenException


def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> User:
    """校验 Bearer JWT 并返回当前用户(对应 NestJS 的 JwtAuthGuard)"""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedException(10003, "未提供认证令牌")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise UnauthorizedException(10002, "Token已过期或无效")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UnauthorizedException(10003, "用户不存在")
    if user.status == "inactive":
        raise UnauthorizedException(10005, "账号已被禁用")
    if user.status == "locked":
        raise UnauthorizedException(10006, "账号已被锁定")
    return user


def require_roles(*roles):
    """角色校验依赖工厂(对应 NestJS 的 @Roles + RolesGuard)"""
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenException(10007, "权限不足")
        return current_user
    return _checker
