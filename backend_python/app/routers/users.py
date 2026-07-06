"""用户路由 — 仅做路由转发，业务逻辑在 crud/user.py"""
from fastapi import APIRouter, Depends, Body, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import User
from ..core.response import ok
from ..schemas.user import (
    UserCreate, UserUpdate, ProfileUpdate, ChangePasswordRequest,
    UpdateUserPasswordRequest, ResetUserPasswordRequest, BatchDeleteRequest,
)
from ..crud import user as user_crud

router = APIRouter()


@router.get("/users")
def get_users(request: Request, db: Session = Depends(get_db)):
    """分页查询用户列表 — 支持角色过滤、关键字搜索、字段排序（需登录）"""
    q = request.query_params
    return ok(user_crud.get_users(
        db, page=int(q.get("page", 1)), limit=int(q.get("limit", 10)),
        role=q.get("role"), keyword=q.get("keyword"),
        sort_field=q.get("sortField", "createdAt"), sort_order=q.get("sortOrder", "desc"),
    ))


@router.get("/users/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前登录用户资料"""
    return ok(current_user.to_dict(exclude={"password"}))


@router.put("/users/profile")
def update_profile(body: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新自己的资料（不可改密码和ID）"""
    return ok(user_crud.update_profile(db, current_user, body.model_dump(exclude_unset=True)))


@router.get("/users/{user_id}")
def get_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """根据 ID 查询用户信息"""
    return ok(user_crud.get_user_by_id(db, user_id).to_dict(exclude={"password"}))


@router.post("/users")
def create_user(body: UserCreate, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """创建用户（仅超级管理员）"""
    return ok(user_crud.create_user(db, body.model_dump()))


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """更新用户信息（仅超级管理员）"""
    return ok(user_crud.update_user(db, user_id, body.model_dump(exclude_unset=True)))


@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """删除用户（仅超级管理员）"""
    return ok(user_crud.delete_user(db, user_id))


@router.put("/users/password")
def change_password(body: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """用户修改自己的密码"""
    return ok(user_crud.change_password(db, current_user, body.currentPassword, body.newPassword))


@router.patch("/users/{user_id}/password")
def update_user_password(user_id: int, body: UpdateUserPasswordRequest, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """管理员修改指定用户密码（仅超级管理员）"""
    return ok(user_crud.update_user_password(db, user_id, body.oldPassword, body.newPassword))


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, body: ResetUserPasswordRequest, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """管理员重置用户密码（仅超级管理员）— 重置后强制改密"""
    return ok(user_crud.reset_user_password(db, user_id, body.newPassword))


@router.post("/users/batch-import")
def import_users_batch(users: list[dict] = Body(...), current_user: User = Depends(require_roles("superadmin", "teacher")), db: Session = Depends(get_db)):
    """批量导入用户（管理员/教师）— 逐条校验唯一性"""
    return ok(user_crud.import_users_batch(db, users))


@router.post("/users/batch-delete")
def delete_users_batch(body: BatchDeleteRequest, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """批量删除用户（仅超级管理员）— 超管不可删"""
    return ok(user_crud.delete_users_batch(db, body.userIds))
