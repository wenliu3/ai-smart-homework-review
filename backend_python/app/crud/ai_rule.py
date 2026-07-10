"""AI 规则 CRUD"""
from sqlalchemy.orm import Session
from ..models import AiRule
from ..core.exceptions import NotFoundException
from ..core.utils import camel_to_snake


def get_list(db: Session, params: dict) -> dict:
    """分页查询 AI 批改规则列表 — 支持状态/可见性/模型类型/关键字过滤"""
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

    total = query.count()
    col = getattr(AiRule, camel_to_snake(sort), AiRule.created_at)
    col = col.asc() if order == "asc" else col.desc()
    items = query.order_by(col).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [r.to_dict() for r in items], "total": total, "page": page, "pageSize": page_size}


def get_available(db: Session, status: str = "active") -> list:
    """查询可用的 AI 规则(用于下拉选择)"""
    rules = db.query(AiRule).filter(AiRule.status == status).all()
    return [r.to_dict() for r in rules]


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


def update(db: Session, rule_id: int, data: dict) -> dict:
    """更新 AI 规则"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(rule, col) and col != "id":
            setattr(rule, col, v)
    db.commit()
    return {"id": str(rule_id), "success": True}


def delete(db: Session, rule_id: int) -> dict:
    """硬删除 AI 规则 — 从数据库中彻底删除"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
    db.delete(rule)
    db.commit()
    return {"id": str(rule_id), "success": True}


def toggle_status(db: Session, rule_id: int) -> dict:
    """切换 AI 规则状态 — active <-> inactive"""
    rule = db.query(AiRule).filter(AiRule.id == rule_id).first()
    if not rule:
        raise NotFoundException(10015, "AI规则不存在")
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
        tags=original.tags, max_score=original.max_score, created_by=original.created_by,
    )
    db.add(new_rule)
    db.commit()
    return {"id": str(new_rule.id), "success": True}
