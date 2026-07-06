"""AI 规则路由 — 仅做路由转发，业务逻辑在 crud/ai_rule.py"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..core.response import ok
from ..schemas.ai_rule import AiRuleCreate, AiRuleUpdate, CopyRuleRequest
from ..crud import ai_rule as ai_rule_crud

router = APIRouter()


@router.get("/v1/ai-rules")
def get_list(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """分页查询 AI 批改规则列表 — 支持状态/可见性/模型类型/关键字过滤"""
    return ok(ai_rule_crud.get_list(db, dict(request.query_params)))


@router.get("/v1/ai-rules/available/list")
def get_available(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询可用的 AI 规则(用于下拉选择)"""
    status = request.query_params.get("status", "active")
    return ok(ai_rule_crud.get_available(db, status))


@router.get("/v1/ai-rules/{rule_id}")
def get_by_id(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """根据 ID 查询 AI 规则"""
    return ok(ai_rule_crud.get_by_id(db, rule_id))


@router.post("/v1/ai-rules")
def create(body: AiRuleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建 AI 批改规则"""
    return ok(ai_rule_crud.create(db, body.model_dump()))


@router.post("/v1/ai-rules/{rule_id}/update")
def update(rule_id: int, body: AiRuleUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新 AI 规则"""
    return ok(ai_rule_crud.update(db, rule_id, body.model_dump(exclude_unset=True)))


@router.post("/v1/ai-rules/{rule_id}/delete")
def delete(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """软删除 AI 规则 — 状态置为 inactive"""
    return ok(ai_rule_crud.delete(db, rule_id))


@router.post("/v1/ai-rules/{rule_id}/copy")
def copy(rule_id: int, body: CopyRuleRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """复制 AI 规则 — 创建副本"""
    return ok(ai_rule_crud.copy(db, rule_id, body.name))
