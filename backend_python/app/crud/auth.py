"""认证 CRUD: 登录/注册/刷新令牌/改密"""
import uuid
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..models import User, RefreshToken
from ..core.security import hash_password, verify_password, create_access_token
from ..core.exceptions import (
    UnauthorizedException, BadRequestException, ConflictException,
)
from ..core.utils import now
from ..config import settings


def cleanup_expired_tokens(db: Session, user_id: int | None = None) -> int:
    """物理删除过期或已撤销的 RefreshToken，避免表无限堆积。

    - user_id 为 None 时清理全局，否则只清理该用户的。
    - 返回删除条数。
    """
    q = db.query(RefreshToken).filter(
        or_(RefreshToken.expires_at < now(), RefreshToken.is_revoked.is_(True))
    )
    if user_id is not None:
        q = q.filter(RefreshToken.user_id == user_id)
    deleted = q.delete()
    db.commit()
    return deleted


def login(db: Session, account: str, password: str) -> dict:
    """用户登录 — 支持用户名/邮箱/学号三种方式，校验密码后签发 JWT + RefreshToken"""
    user = db.query(User).filter(
        or_(User.username == account, User.email == account, User.student_id == account)
    ).first()
    if not user:
        raise UnauthorizedException(10003, "账号或密码错误")
    if user.status == "inactive":
        raise UnauthorizedException(10005, "账号已被禁用，请联系管理员")
    if user.status == "locked":
        raise UnauthorizedException(10006, "账号已被锁定，请联系管理员")
    if not verify_password(password, user.password):
        raise UnauthorizedException(10003, "账号或密码错误")

    is_first_login = not user.last_login
    user.last_login = now()
    if is_first_login:
        user.first_login_at = user.last_login

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.is_revoked.is_(False)
    ).update({RefreshToken.is_revoked: True})
    # 物理清理该用户所有过期/已撤销的 token，避免表堆积
    cleanup_expired_tokens(db, user_id=user.id)

    refresh_str = str(uuid.uuid4())
    expires_in = settings.JWT_REFRESH_EXPIRES_IN
    expires_at = now() + timedelta(seconds=expires_in)
    db.add(RefreshToken(user_id=user.id, token=refresh_str, expires_at=expires_at))
    db.commit()

    token = create_access_token(str(user.id), user.username, user.role)
    return {
        "token": token, "refreshToken": refresh_str,
        "expiresIn": settings.JWT_EXPIRES_IN, "userId": str(user.id),
        "mustChangePassword": user.must_change_password,
        "isFirstLogin": is_first_login,
        "user": {
            "id": str(user.id), "username": user.username, "email": user.email,
            "name": user.name, "role": user.role,
            "mustChangePassword": user.must_change_password,
        },
    }


def logout(db: Session, user_id: int) -> dict:
    """退出登录 — 撤销该用户所有未过期的 RefreshToken"""
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False)
    ).update({RefreshToken.is_revoked: True})
    db.commit()
    return {"success": True}


def refresh_token(db: Session, refresh_str: str) -> dict:
    """刷新令牌 — 校验旧 RefreshToken 有效后签发新的 JWT + RefreshToken"""
    stored = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_str, RefreshToken.is_revoked.is_(False)
    ).first()
    if not stored:
        raise UnauthorizedException(10004, "刷新令牌无效或已过期")
    if now() > stored.expires_at:
        stored.is_revoked = True
        db.commit()
        raise UnauthorizedException(10004, "刷新令牌已过期，请重新登录")

    user = db.query(User).filter(User.id == stored.user_id).first()
    if not user:
        raise UnauthorizedException(10003, "用户不存在")

    # 撤销该用户所有有效 token（不止当前 stored），确保刷新后只保留一个新 token
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.is_revoked.is_(False)
    ).update({RefreshToken.is_revoked: True})
    # 物理清理该用户所有过期/已撤销的 token
    cleanup_expired_tokens(db, user_id=user.id)
    new_refresh = str(uuid.uuid4())
    expires_in = settings.JWT_REFRESH_EXPIRES_IN
    expires_at = now() + timedelta(seconds=expires_in)
    db.add(RefreshToken(user_id=user.id, token=new_refresh, expires_at=expires_at))
    db.commit()

    token = create_access_token(str(user.id), user.username, user.role)
    return {"token": token, "refreshToken": new_refresh, "expiresIn": expires_in}


def get_profile(db: Session, user: User) -> dict:
    """获取当前登录用户信息(不含密码)"""
    u = user
    return {"user": {
        "_id": str(u.id), "id": str(u.id),
        "username": u.username, "name": u.name, "email": u.email,
        "role": u.role, "status": u.status, "studentId": u.student_id,
        "phone": u.phone, "avatar": u.avatar,
        "mustChangePassword": u.must_change_password,
        "firstLoginAt": u.first_login_at.isoformat() if u.first_login_at else None,
        "lastLogin": u.last_login.isoformat() if u.last_login else None,
        "createdAt": u.created_at.isoformat() if u.created_at else None,
        "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
    }}


def change_password(db: Session, user: User, current_password: str, new_password: str) -> dict:
    """修改密码 — 校验原密码后更新为新密码"""
    if not verify_password(current_password, user.password):
        raise BadRequestException(10008, "当前密码错误")
    user.password = hash_password(new_password)
    db.commit()
    return {"message": "密码修改成功"}


def first_change_password(db: Session, user: User, current_password: str, new_password: str) -> dict:
    """首次登录强制改密 — 改密后将 mustChangePassword 置为 False"""
    if not verify_password(current_password, user.password):
        raise BadRequestException(10008, "原密码错误")
    user.password = hash_password(new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "密码修改成功，请重新登录"}


def register(db: Session, username: str, password: str, email: str, name: str | None) -> dict:
    """用户注册 — 校验用户名/邮箱唯一性后创建学生账号并签发 JWT"""
    existing = db.query(User).filter(or_(User.username == username, User.email == email)).first()
    if existing:
        raise ConflictException(10009, "用户名或邮箱已存在")
    user = User(
        username=username, email=email, password=hash_password(password),
        name=name or username, role="student", status="active",
    )
    db.add(user)
    db.commit()
    token = create_access_token(str(user.id), user.username, user.role)
    return {
        "token": token, "success": True, "message": "注册成功",
        "userId": str(user.id), "expiresIn": settings.JWT_EXPIRES_IN,
    }


def register_legacy(db: Session, email: str, name: str, password: str) -> dict:
    """兼容旧版注册 API — 以邮箱作为用户名"""
    existing = db.query(User).filter(or_(User.username == email, User.email == email)).first()
    if existing:
        raise ConflictException(10009, "用户名或邮箱已存在")
    user = User(
        username=email, email=email, password=hash_password(password),
        name=name, role="student", status="active",
    )
    db.add(user)
    db.commit()
    token = create_access_token(str(user.id), user.username, user.role)
    return {"token": token, "userId": str(user.id), "expiresIn": settings.JWT_EXPIRES_IN}
