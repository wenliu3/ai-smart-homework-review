"""AI 模型 CRUD"""
import time
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import requests
from ..models import AiModel
from ..core.exceptions import NotFoundException
from ..core.utils import camel_to_snake

logger = logging.getLogger(__name__)

# 密钥字段：响应中脱敏，且客户端回传掩码值时不落库
_SECRET_COLUMNS = ("api_key", "access_key", "secret_key")

# /active 端点（教师可访问）只返回的非敏感字段（camelCase）
_ACTIVE_PUBLIC_FIELDS = ("code", "name", "provider", "modelName", "status", "isDefault")


def _is_masked_value(value) -> bool:
    """判断客户端回传的密钥值是否为脱敏掩码或空值（是则跳过更新，防止掩码入库）。"""
    if not value or not isinstance(value, str) or not value.strip():
        return True
    return "****" in value


def _to_public_dict(model: AiModel) -> dict:
    """序列化模型配置：排除明文密钥列，补充掩码值供前端展示。"""
    from ..agent.gateway import mask_secret
    data = model.to_dict(exclude=set(_SECRET_COLUMNS))
    data["apiKey"] = mask_secret(model.api_key)
    data["accessKey"] = mask_secret(model.access_key)
    data["secretKey"] = mask_secret(model.secret_key)
    return data


def get_list(db: Session) -> dict:
    """查询所有 AI 模型列表 — 含汇总统计(总数/在线数/总用量/总余额)，密钥脱敏"""
    models = db.query(AiModel).all()
    active = sum(1 for m in models if m.status == "active")
    total_usage = sum((m.total_usage or 0) for m in models)
    total_balance = sum((m.last_balance or 0) for m in models)
    return {
        "models": [_to_public_dict(m) for m in models],
        "summary": {"totalModels": len(models), "activeModels": active, "totalUsage": total_usage, "totalBalance": total_balance},
    }


def get_active(db: Session) -> list:
    """查询所有激活状态的 AI 模型 — 教师端下拉框使用，只返回非敏感字段"""
    models = db.query(AiModel).filter(AiModel.status == "active").all()
    return [
        {key: m.to_dict().get(key) for key in _ACTIVE_PUBLIC_FIELDS}
        for m in models
    ]


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
    """根据 code 查询单个 AI 模型配置（密钥脱敏）"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    return _to_public_dict(model)


def update_config(db: Session, code: str, data: dict) -> dict:
    """更新 AI 模型配置(API Key/状态等) — 含 isDefault 互斥逻辑

    密钥字段回传掩码值（如 "sk-1****cdef"）或空值时跳过更新，
    防止前端把脱敏后的展示值写回数据库覆盖真实密钥。
    """
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")

    # 如果设为默认，先清除其他模型的默认标记
    if data.get("isDefault"):
        db.query(AiModel).filter(AiModel.is_default.is_(True)).update(
            {AiModel.is_default: False}
        )

    for k, v in data.items():
        col = camel_to_snake(k)
        if col in _SECRET_COLUMNS and _is_masked_value(v):
            continue
        if hasattr(model, col) and col != "id":
            setattr(model, col, v)
    db.commit()
    return _to_public_dict(model)


def set_default(db: Session, code: str) -> dict:
    """设置默认 AI 模型 — 先取消其他模型的默认标记"""
    db.query(AiModel).filter(AiModel.is_default.is_(True)).update({AiModel.is_default: False})
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    model.is_default = True
    db.commit()
    return {"success": True, "message": f"已将 {model.name} 设为默认模型"}


def _make_api_request(url: str, api_key: str, timeout: int = 10) -> requests.Response:
    """统一的 API 请求封装 — Bearer token 鉴权"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.get(url, headers=headers, timeout=timeout)


def get_balance(db: Session, code: str) -> dict:
    """查询 AI 模型余额 — DeepSeek 走官方 billing API，其他走 /models 健康检查"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")

    if not model.api_key:
        return {
            "balance": model.last_balance,
            "currency": model.balance_currency,
            "lastUpdated": model.last_balance_check.isoformat() if model.last_balance_check else None,
            "status": "error",
            "message": "未配置 API Key",
        }

    now = datetime.now(timezone.utc)

    try:
        if model.provider and "deepseek" in model.provider.lower():
            # DeepSeek 官方 billing API
            resp = _make_api_request(
                "https://api.deepseek.com/user/balance",
                model.api_key,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                infos = data.get("balance_infos", [])
                if infos:
                    info = infos[0]
                    balance = float(info.get("total_balance", 0))
                else:
                    balance = float(data.get("total_balance", 0))

                model.last_balance = balance
                model.last_balance_check = now
                db.commit()

                return {
                    "balance": balance,
                    "currency": info.get("currency", "CNY") if infos else "CNY",
                    "lastUpdated": now.isoformat(),
                    "status": "success",
                    "details": {
                        "grantedBalance": float(info.get("granted_balance", 0)) if infos else 0,
                        "toppedUpBalance": float(info.get("topped_up_balance", 0)) if infos else 0,
                    } if infos else {},
                }
            else:
                return {
                    "balance": model.last_balance,
                    "currency": model.balance_currency,
                    "lastUpdated": model.last_balance_check.isoformat() if model.last_balance_check else None,
                    "status": "error",
                    "message": f"余额查询失败: HTTP {resp.status_code}",
                }
        else:
            # 其他提供商：尝试 /v1/models 端点确认连通性，余额返回缓存值
            base = (model.base_url or "").rstrip("/")
            try:
                _make_api_request(f"{base}/models", model.api_key, timeout=5)
            except Exception:
                pass  # 连通性检查不影响余额展示

            model.last_balance_check = now
            db.commit()

            return {
                "balance": model.last_balance,
                "currency": model.balance_currency,
                "lastUpdated": now.isoformat(),
                "status": "success",
                "message": "当前提供商不支持自动查询余额，显示为上次缓存值",
            }
    except requests.Timeout:
        return {
            "balance": model.last_balance,
            "currency": model.balance_currency,
            "lastUpdated": model.last_balance_check.isoformat() if model.last_balance_check else None,
            "status": "error",
            "message": "余额查询超时",
        }
    except Exception as e:
        logger.error(f"查询余额失败 [{code}]: {e}")
        return {
            "balance": model.last_balance,
            "currency": model.balance_currency,
            "lastUpdated": model.last_balance_check.isoformat() if model.last_balance_check else None,
            "status": "error",
            "message": f"查询失败: {str(e)}",
        }


def test_connection(db: Session, code: str) -> dict:
    """测试 AI 模型连接 — 向模型 API 发送真实请求验证连通性"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")

    if not model.api_key:
        return {"success": False, "responseTime": 0, "message": "未配置 API Key"}

    base = (model.base_url or "").rstrip("/")
    # 尝试多个常见端点
    endpoints = ["/models", "/v1/models"]
    last_error = None

    for ep in endpoints:
        url = f"{base}{ep}"
        try:
            start = time.time()
            resp = _make_api_request(url, model.api_key, timeout=10)
            elapsed_ms = round((time.time() - start) * 1000)

            if resp.status_code == 200:
                return {
                    "success": True,
                    "responseTime": elapsed_ms,
                    "message": f"连接正常 ({ep})",
                }
            elif resp.status_code == 401:
                return {
                    "success": False,
                    "responseTime": elapsed_ms,
                    "message": f"认证失败: API Key 无效 (HTTP 401)",
                }
            last_error = f"HTTP {resp.status_code}"
        except requests.Timeout:
            last_error = "连接超时"
        except requests.ConnectionError:
            last_error = "无法连接服务器"
        except Exception as e:
            last_error = str(e)

    return {
        "success": False,
        "responseTime": 0,
        "message": f"连接失败: {last_error}",
    }


def get_stats(db: Session, code: str) -> dict:
    """查询 AI 模型使用统计(日/月用量，当前返回空列表)"""
    model = db.query(AiModel).filter(AiModel.code == code).first()
    if not model:
        raise NotFoundException(10015, "模型不存在")
    return {"dailyUsage": [], "monthlyUsage": [], "recentActivity": []}


def increment_usage(db: Session, model_id: int, calls: int, tokens: int) -> None:
    """原子累加模型调用次数与 Token 总量（规划 4.1）。

    多 worker 并发安全：单条 UPDATE 自增，不做读-改-写。
    统计尽力而为，任何失败由调用方吞掉，不影响业务运行。
    """
    from sqlalchemy import func, update as sa_update

    if calls <= 0 and tokens <= 0:
        return
    db.execute(
        sa_update(AiModel)
        .where(AiModel.id == model_id)
        .values(
            total_usage=func.coalesce(AiModel.total_usage, 0) + max(calls, 0),
            total_tokens=func.coalesce(AiModel.total_tokens, 0) + max(tokens, 0),
            last_used_at=datetime.now(),
        )
    )
    db.commit()
