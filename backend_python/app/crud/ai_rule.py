"""AI 规则 CRUD"""
from sqlalchemy.orm import Session
from ..models import AiRule
from ..core.exceptions import NotFoundException, ForbiddenException
from ..core.utils import camel_to_snake


def _assert_rule_owner(rule: AiRule, actor_id: int | None, actor_role: str | None) -> None:
    """写操作归属校验：仅创建人或超级管理员可修改/删除/启停规则。

    系统规则（visibility=system，官方内置）仅超级管理员可管理。
    """
    if rule.visibility == "system" and actor_role != "superadmin":
        raise ForbiddenException(10007, "系统规则仅超级管理员可管理")
    if actor_role == "superadmin":
        return
    created_by = rule.created_by or {}
    if actor_id is None or str(created_by.get("id")) != str(actor_id):
        raise ForbiddenException(10007, "只能操作自己创建的AI规则")


def _visible_to(rule: AiRule, actor_id: int | None, actor_role: str | None) -> bool:
    """可见性规则：私有规则仅创建人与超级管理员可见，公开/系统规则所有人可见"""
    if rule.visibility != "private":
        return True
    if actor_role == "superadmin":
        return True
    created_by = rule.created_by or {}
    return actor_id is not None and str(created_by.get("id")) == str(actor_id)


def get_list(db: Session, params: dict, actor_id: int | None = None, actor_role: str | None = None) -> dict:
    """分页查询 AI 批改规则列表 — 支持状态/可见性/模型类型/关键字过滤。

    私有规则仅创建人与超级管理员可见（可见性字段的真实语义）。
    """
    page = int(params.get("page", 1))
    page_size = int(params.get("pageSize", 10))
    sort = params.get("sort", "createdAt")
    order = params.get("order", "desc")

    query = db.query(AiRule)
    if params.get("status"):
        query = query.filter(AiRule.status == params["status"])
    if params.get("visibility"):
        query = query.filter(AiRule.visibility == params["visibility"])
    if params.get("modelType"):
        query = query.filter(AiRule.model_type == params["modelType"])
    if params.get("search"):
        query = query.filter(AiRule.name.ilike(f"%{params['search']}%"))
    rules = [r for r in query.all() if _visible_to(r, actor_id, actor_role)]

    total = len(rules)
    col_name = camel_to_snake(sort)
    reverse = order != "asc"
    rules.sort(key=lambda r: ((v := getattr(r, col_name, None) or r.created_at) is None, v), reverse=reverse)
    start = (page - 1) * page_size
    items = rules[start:start + page_size]
    return {"items": [r.to_dict() for r in items], "total": total, "page": page, "pageSize": page_size}


def get_available(db: Session, status: str = "active", actor_id: int | None = None, actor_role: str | None = None) -> list:
    """查询可用的 AI 规则(用于下拉选择) — 私有规则仅创建人与超级管理员可见"""
    rules = db.query(AiRule).filter(AiRule.status == status).all()
    return [r.to_dict() for r in rules if _visible_to(r, actor_id, actor_role)]


def get_by_id(db: Session, rule_id: int) -> dict:
    """根据 ID 查询 AI 规则"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
    return rule.to_dict()


def create(db: Session, data: dict) -> dict:
    """创建 AI 批改规则"""
    rule = AiRule()
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(rule, col) and col != "id":
            setattr(rule, col, v)
    db.add(rule)
    db.commit()
    return {"id": str(rule.id), "success": True}


def update(db: Session, rule_id: int, data: dict, actor_id: int | None = None, actor_role: str | None = None) -> dict:
    """更新 AI 规则 — 仅创建人或超级管理员"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
    _assert_rule_owner(rule, actor_id, actor_role)
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(rule, col) and col != "id":
            setattr(rule, col, v)
    db.commit()
    return {"id": str(rule_id), "success": True}


def delete(db: Session, rule_id: int, actor_id: int | None = None, actor_role: str | None = None) -> dict:
    """硬删除 AI 规则 — 从数据库中彻底删除；仅创建人或超级管理员"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
    _assert_rule_owner(rule, actor_id, actor_role)
    db.delete(rule)
    db.commit()
    return {"id": str(rule_id), "success": True}


def toggle_status(db: Session, rule_id: int, actor_id: int | None = None, actor_role: str | None = None) -> dict:
    """切换 AI 规则状态 — active <-> inactive；仅创建人或超级管理员"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
    _assert_rule_owner(rule, actor_id, actor_role)
    rule.status = "inactive" if rule.status == "active" else "active"
    db.commit()
    return {"id": str(rule_id), "status": rule.status, "success": True}


def copy(db: Session, rule_id: int, name: str | None) -> dict:
    """复制 AI 规则 — 创建副本，状态默认 inactive"""
    original = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not original:
        raise NotFoundException(10015, "AI规则不存在")
    new_rule = AiRule(
        name=name or f"{original.name} (副本)",
        description=original.description, model_type=original.model_type,
        prompt=original.prompt, status="inactive", visibility="private",
        tags=original.tags, max_score=original.max_score,
        criteria=original.criteria, created_by=original.created_by,
    )
    db.add(new_rule)
    db.commit()
    return {"id": str(new_rule.id), "success": True}
