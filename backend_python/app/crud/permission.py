"""权限 CRUD: 菜单/角色/用户资源"""
from sqlalchemy.orm import Session
from ..models import User, Role, Menu
from ..core.exceptions import NotFoundException, ConflictException
from ..core.utils import camel_to_snake


def _build_menu_tree(menus):
    """根据 parentId 将扁平菜单列表构建为树形结构"""
    tree, by_id = [], {}
    for m in menus:
        d = m.to_dict()
        d["children"] = []
        by_id[m.id] = d
    for m in menus:
        d = by_id[m.id]
        pid = m.parent_id
        if pid and pid in by_id:
            by_id[pid]["children"].append(d)
        else:
            tree.append(d)
    return tree


def _resolve_user_id(user_id: str, current_user: User) -> int:
    """将 'current' 解析为当前登录用户 ID，否则转为整数"""
    return current_user.id if user_id == "current" else int(user_id)


def get_user_resources(db: Session, user_id: str, current_user: User) -> dict:
    """获取用户资源 — 根据用户角色查询关联的角色/权限/菜单树"""
    uid = _resolve_user_id(user_id, current_user)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        return {"roles": [], "permissions": [], "menus": []}
    roles = db.query(Role).filter(Role.code == user.role).all()
    menu_ids = []
    for r in roles:
        menu_ids.extend([int(x) for x in (r.menu_ids or [])])
    menus = db.query(Menu).filter(Menu.id.in_(menu_ids), Menu.status == "active").order_by(Menu.sort.asc()).all()
    permissions = []
    for r in roles:
        permissions.extend(r.permissions or [])
    return {
        "roles": [{"_id": str(r.id), "id": str(r.id), "name": r.name, "code": r.code} for r in roles],
        "permissions": list(set(permissions)),
        "menus": _build_menu_tree(menus),
    }


def get_user_roles(db: Session, user_id: str, current_user: User) -> list:
    """获取用户所属角色列表"""
    uid = _resolve_user_id(user_id, current_user)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        return []
    roles = db.query(Role).filter(Role.code == user.role).all()
    return [r.to_dict() for r in roles]


def get_user_menus(db: Session, user_id: str, current_user: User) -> list:
    """获取用户可访问的菜单树"""
    uid = _resolve_user_id(user_id, current_user)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        return []
    roles = db.query(Role).filter(Role.code == user.role).all()
    menu_ids = []
    for r in roles:
        menu_ids.extend([int(x) for x in (r.menu_ids or [])])
    menus = db.query(Menu).filter(Menu.id.in_(menu_ids), Menu.status == "active").order_by(Menu.sort.asc()).all()
    return _build_menu_tree(menus)


def get_user_permissions(db: Session, user_id: str, current_user: User) -> list:
    """获取用户权限列表(去重)"""
    uid = _resolve_user_id(user_id, current_user)
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        return []
    roles = db.query(Role).filter(Role.code == user.role).all()
    permissions = []
    for r in roles:
        permissions.extend(r.permissions or [])
    return list(set(permissions))


# ===== 菜单管理 =====

def get_menus(db: Session, params: dict) -> list | dict:
    """查询菜单列表 — 支持名称/路径/状态/类型过滤，tree=true 时返回树形结构"""
    query = db.query(Menu)
    if params.get("name"):
        query = query.filter(Menu.name.ilike(f"%{params['name']}%"))
    if params.get("path"):
        query = query.filter(Menu.path.ilike(f"%{params['path']}%"))
    if params.get("status"):
        query = query.filter(Menu.status == params["status"])
    if params.get("hidden") is not None:
        query = query.filter(Menu.hidden.is_(params["hidden"] == "true"))
    if params.get("type"):
        query = query.filter(Menu.type == params["type"])
    menus = query.order_by(Menu.sort.asc()).all()
    if params.get("tree") == "true":
        return _build_menu_tree(menus)
    return [m.to_dict() for m in menus]


def get_menu_by_id(db: Session, menu_id: int) -> dict:
    """根据 ID 查询菜单"""
    menu = db.query(Menu).filter(Menu.id == menu_id).first()
    if not menu:
        raise NotFoundException(10015, "菜单不存在")
    return menu.to_dict()


def create_menu(db: Session, data: dict) -> dict:
    """创建菜单 — 校验 code 唯一性"""
    existing = db.query(Menu).filter(Menu.code == data.get("code")).first()
    if existing:
        raise ConflictException(10009, "菜单编码已存在")
    menu = Menu()
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(menu, col) and col != "id":
            setattr(menu, col, v)
    db.add(menu)
    db.commit()
    return menu.to_dict()


def update_menu(db: Session, menu_id: int, data: dict) -> dict:
    """更新菜单信息"""
    menu = db.query(Menu).filter(Menu.id == menu_id).first()
    if not menu:
        raise NotFoundException(10015, "菜单不存在")
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(menu, col) and col != "id":
            setattr(menu, col, v)
    db.commit()
    return menu.to_dict()


def delete_menu(db: Session, menu_id: int) -> dict:
    """删除菜单"""
    menu = db.query(Menu).filter(Menu.id == menu_id).first()
    if not menu:
        raise NotFoundException(10015, "菜单不存在")
    db.delete(menu)
    db.commit()
    return {"success": True}


# ===== 角色管理 =====

def get_roles(db: Session, params: dict) -> dict:
    """分页查询角色列表 — 支持搜索/状态/是否系统角色过滤"""
    page = int(params.get("page", 1))
    limit = int(params.get("limit", 20))
    query = db.query(Role)
    if params.get("search"):
        query = query.filter(Role.name.ilike(f"%{params['search']}%"))
    if params.get("status"):
        query = query.filter(Role.status == params["status"])
    if params.get("isSystem") is not None:
        query = query.filter(Role.is_system.is_(params["isSystem"] == "true"))
    total = query.count()
    items = query.order_by(Role.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [r.to_dict() for r in items], "total": total, "page": page, "limit": limit}


def get_role_by_id(db: Session, role_id: int) -> dict:
    """根据 ID 查询角色"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException(10015, "角色不存在")
    return role.to_dict()


def get_role_with_menus(db: Session, role_id: int) -> dict:
    """查询角色及其关联的菜单列表"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException(10015, "角色不存在")
    menu_ids = [int(x) for x in (role.menu_ids or [])]
    menus = db.query(Menu).filter(Menu.id.in_(menu_ids)).all()
    d = role.to_dict()
    d["menus"] = [m.to_dict() for m in menus]
    return d


def create_role(db: Session, data: dict) -> dict:
    """创建角色 — 校验 code 唯一性"""
    existing = db.query(Role).filter(Role.code == data.get("code")).first()
    if existing:
        raise ConflictException(10009, "角色编码已存在")
    role = Role()
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(role, col) and col != "id":
            setattr(role, col, v)
    db.add(role)
    db.commit()
    return role.to_dict()


def update_role(db: Session, role_id: int, data: dict) -> dict:
    """更新角色信息"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException(10015, "角色不存在")
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(role, col) and col != "id":
            setattr(role, col, v)
    db.commit()
    return role.to_dict()


def delete_role(db: Session, role_id: int) -> dict:
    """删除角色 — 系统内置角色不可删除"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException(10015, "角色不存在")
    if role.is_system:
        raise ConflictException(10011, "系统内置角色不可删除")
    db.delete(role)
    db.commit()
    return {"success": True}


def assign_menus(db: Session, role_id: int, menu_ids: list[str]) -> dict:
    """为角色分配菜单 — 同时更新 menuIds 和 permissions"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException(10015, "角色不存在")
    role.menu_ids = menu_ids
    role.permissions = menu_ids
    db.commit()
    return role.to_dict()
