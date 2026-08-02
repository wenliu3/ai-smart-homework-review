"""AI 模型路由 — 仅做路由转发，业务逻辑在 crud/ai_model.py

权限：模型配置含 API Key 等敏感凭据，全部端点仅限超级管理员；
唯一例外是 /active（教师端 AI 规则表单的模型下拉框需要），
对教师开放但只返回非敏感字段。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_roles
from ..models import User
from ..core.response import ok
from ..schemas.ai_model import AiModelUpdate, GradingStructurerBindingUpdate
from ..crud import ai_model as ai_model_crud

router = APIRouter()


@router.get("/admin/ai-models")
def get_list(current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """查询所有 AI 模型列表 — 含汇总统计（密钥脱敏）"""
    return ok(ai_model_crud.get_list(db))


@router.get("/admin/ai-models/active")
def get_active(current_user: User = Depends(require_roles("teacher", "superadmin")), db: Session = Depends(get_db)):
    """查询激活状态的 AI 模型 — 教师可用，只返回非敏感字段"""
    return ok(ai_model_crud.get_active(db))


@router.post("/admin/ai-models/initialize")
def initialize(current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """初始化预置 AI 模型(DeepSeek + 豆包)"""
    return ok(ai_model_crud.initialize(db))


@router.get("/admin/ai-models/grading-structurer/config")
def get_grading_structurer_config(current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """查询独立结构化模型绑定配置"""
    return ok(ai_model_crud.get_grading_structurer_binding(db))


@router.put("/admin/ai-models/grading-structurer/config")
def update_grading_structurer_config(body: GradingStructurerBindingUpdate, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """更新独立结构化模型绑定配置"""
    return ok(ai_model_crud.set_grading_structurer_binding(db, enabled=body.enabled, model_code=body.modelCode))


@router.post("/admin/ai-models/{code}/test-structured-output")
def test_structured_output(code: str, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """结构化输出能力测试 — 只用所选模型 + 固定无业务数据 Prompt，返回 success/摘要，绝不含原始输出"""
    return ok(ai_model_crud.test_structured_output(db, code))


@router.get("/admin/ai-models/{code}")
def get_detail(code: str, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """根据 code 查询单个 AI 模型配置（密钥脱敏）"""
    return ok(ai_model_crud.get_detail(db, code))


@router.put("/admin/ai-models/{code}")
def update_config(code: str, body: AiModelUpdate, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """更新 AI 模型配置(API Key/状态等)"""
    return ok(ai_model_crud.update_config(db, code, body.model_dump(exclude_unset=True)))


@router.post("/admin/ai-models/{code}/default")
def set_default(code: str, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """设置默认 AI 模型"""
    return ok(ai_model_crud.set_default(db, code))


@router.get("/admin/ai-models/{code}/balance")
def get_balance(code: str, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """查询 AI 模型余额"""
    return ok(ai_model_crud.get_balance(db, code))


@router.post("/admin/ai-models/{code}/test")
def test_connection(code: str, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """测试 AI 模型连接"""
    return ok(ai_model_crud.test_connection(db, code))


@router.get("/admin/ai-models/{code}/stats")
def get_stats(code: str, current_user: User = Depends(require_roles("superadmin")), db: Session = Depends(get_db)):
    """查询 AI 模型使用统计"""
    return ok(ai_model_crud.get_stats(db, code))
