"""AI 模型 CRUD"""
from sqlalchemy.orm import Session
from ..models import AiModel
from ..core.exceptions import NotFoundException
from ..core.utils import camel_to_snake


def get_list(db: Session) -> dict:
    """查询所有 AI 模型列表 — 含汇总统计(总数/在线数/总用量/总余额)"""
    models = db.query(AiModel).all()
    active = sum(1 for m in models if m.status == "active")
    total_usage = sum((m.total_usage or 0) for m in models)
    total_balance = sum((m.last_balance or 0) for m in models)
    return {
        "models": [m.to_dict() for m in models],
        "summary": {"totalModels": len(models), "activeModels": active, "totalUsage": total_usage, "totalBalance": total_balance},
    }


def get_active(db: Session) -> list:
    """查询所有激活状态的 AI 模型"""
    models = db.query(AiModel).filter(AiModel.status == "active").all()
    return [m.to_dict() for m in models]


def initialize(db: Session) -> dict:
    """初始化预置 AI 模型(DeepSeek + 小米) — 已存在则跳过"""
    presets = [
        {"code": "deepseek", "name": "DeepSeek", "provider": "DeepSeek", "model_name": "deepseek-chat", "base_url": "https://api.deepseek.com", "status": "active", "is_default": True},
        {"code": "mimo", "name": "小米", "provider": "小米", "model_name": "mimo-v2.5", "base_url": "https://api.xiaomimimo.com/v1", "status": "active"},
    ]
    for m in presets:
        if not db.query(AiModel).filter(AiModel.code == m["code"]).first():
            db.add(AiModel(**m))
    db.commit()
    return {"success": True, "message": "预置模型初始化完成"}


def get_detail(db: Session, code: str) -> dict:
    """根据 code 查询单个 AI 模型配置"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    return model.to_dict()


def update_config(db: Session, code: str, data: dict) -> dict:
    """更新 AI 模型配置(API Key/状态等)"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    for k, v in data.items():
        col = camel_to_snake(k)
        if hasattr(model, col) and col != "id":
            setattr(model, col, v)
    db.commit()
    return model.to_dict()


def set_default(db: Session, code: str) -> dict:
    """设置默认 AI 模型 — 先取消其他模型的默认标记"""
    db.query(AiModel).filter(AiModel.is_default.is_(True)).update({AiModel.is_default: False})
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    model.is_default = True
    db.commit()
    return {"success": True, "message": f"已将 {model.name} 设为默认模型"}


def get_balance(db: Session, code: str) -> dict:
    """查询 AI 模型余额"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    return {
        "balance": model.last_balance, "currency": model.balance_currency,
        "lastUpdated": model.last_balance_check.isoformat() if model.last_balance_check else None,
        "status": "success",
    }


def test_connection(db: Session, code: str) -> dict:
    """测试 AI 模型连接(当前为模拟返回)"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    return {"success": True, "responseTime": 0, "message": "连接正常"}


def get_stats(db: Session, code: str) -> dict:
    """查询 AI 模型使用统计(日/月用量，当前返回空列表)"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    return {"dailyUsage": [], "monthlyUsage": [], "recentActivity": []}
