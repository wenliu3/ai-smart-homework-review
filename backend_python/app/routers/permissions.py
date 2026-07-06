"""权限路由 — 仅做路由转发，业务逻辑在 crud/permission.py"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..schemas.permission import MenuCreate, MenuUpdate, RoleCreate, RoleUpdate, AssignMenusRequest
from ..crud import permission as permission_crud

router = APIRouter()


# ===== 用户资源接口 =====
@router.get("/permissions/user-roles/users/{user_id}/resources")
def get_user_resources(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户资源 — 角色/权限/菜单树(user_id=current 表示当前用户)"""
    return ok(permission_crud.get_user_resources(db, user_id, current_user))


@router.get("/permissions/user-roles/users/{user_id}/roles")
def get_user_roles(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户所属角色列表"""
    return ok(permission_crud.get_user_roles(db, user_id, current_user))


@router.get("/permissions/user-roles/users/{user_id}/menus")
def get_user_menus(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户可访问的菜单树"""
    return ok(permission_crud.get_user_menus(db, user_id, current_user))


@router.get("/permissions/user-roles/users/{user_id}/permissions")
def get_user_permissions(user_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取用户权限列表(去重)"""
    return ok(permission_crud.get_user_permissions(db, user_id, current_user))


# ===== 菜单管理 =====
@router.get("/permissions/menus")
def get_menus(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询菜单列表 — tree=true 返回树形结构"""
    return ok(permission_crud.get_menus(db, dict(request.query_params)))


@router.get("/permissions/menus/{menu_id}")
def get_menu_by_id(menu_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """根据 ID 查询菜单"""
    return ok(permission_crud.get_menu_by_id(db, menu_id))


@router.post("/permissions/menus")
def create_menu(body: MenuCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建菜单 — 校验 code 唯一性"""
    return ok(permission_crud.create_menu(db, body.model_dump()))


@router.put("/permissions/menus/{menu_id}")
def update_menu(menu_id: int, body: MenuUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新菜单信息"""
    return ok(permission_crud.update_menu(db, menu_id, body.model_dump(exclude_unset=True)))


@router.delete("/permissions/menus/{menu_id}")
def delete_menu(menu_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除菜单"""
    return ok(permission_crud.delete_menu(db, menu_id))


# ===== 角色管理 =====
@router.get("/permissions/roles")
def get_roles(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """分页查询角色列表 — 支持搜索/状态过滤"""
    return ok(permission_crud.get_roles(db, dict(request.query_params)))


@router.get("/permissions/roles/{role_id}")
def get_role_by_id(role_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """根据 ID 查询角色"""
    return ok(permission_crud.get_role_by_id(db, role_id))


@router.get("/permissions/roles/{role_id}/with-menus")
def get_role_with_menus(role_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询角色及其关联的菜单"""
    return ok(permission_crud.get_role_with_menus(db, role_id))


@router.post("/permissions/roles")
def create_role(body: RoleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建角色 — 校验 code 唯一性"""
    return ok(permission_crud.create_role(db, body.model_dump()))


@router.put("/permissions/roles/{role_id}")
def update_role(role_id: int, body: RoleUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新角色信息"""
    return ok(permission_crud.update_role(db, role_id, body.model_dump(exclude_unset=True)))


@router.delete("/permissions/roles/{role_id}")
def delete_role(role_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除角色 — 系统内置角色不可删"""
    return ok(permission_crud.delete_role(db, role_id))


@router.put("/permissions/roles/{role_id}/menus")
def assign_menus(role_id: int, body: AssignMenusRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """为角色分配菜单 — 同时更新 menuIds 和 permissions"""
    return ok(permission_crud.assign_menus(db, role_id, body.menuIds))
