"""新版助手 API 的请求/响应 Schema（规格 13.1）。

所有身份字段（user_id / teacher_id / student_id）绝不出现在请求体中——
身份只来自 `Depends(require_roles(...))` 的认证上下文。
"""
from typing import Literal

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    """启动一次助手运行。session_id 格式由路由层校验（返回 400 而非 422）。"""
    message: str = Field(min_length=1, max_length=4000)
    session_id: str
    # 用户当前所在页面（规划 5.6）：仅作为提示上下文，非权限依据
    page_context: str | None = Field(
        default=None, alias="pageContext", max_length=200,
    )


class CreateSessionRequest(BaseModel):
    """创建新会话。title 可选，默认"新会话"。"""
    title: str = Field(default="新会话", max_length=255)


class RenameSessionRequest(BaseModel):
    """重命名会话。空白标题由路由层拒绝（400 而非 422）。"""
    title: str = Field(max_length=255)


class ContentAccessRequest(BaseModel):
    """受控正文访问：理由必填（空白由路由层拒绝为 400）。"""
    reason: str = Field(max_length=500)


class SubmitFeedbackRequest(BaseModel):
    """运行反馈：👍=1 / 👎=-1，其余取值 422。"""
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=500)


class RunResponse(BaseModel):
    """运行详情。"""
    run_id: str
    status: str
    final_answer: str | None = None
    error_code: str | None = None
    intent: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class SessionResponse(BaseModel):
    """会话概要。"""
    session_id: str
    title: str
    status: str
    message_count: int = 0


class CreateActionDraftRequest(BaseModel):
    action_type: str = Field(alias="actionType")
    target_type: str = Field(alias="targetType", min_length=1, max_length=64)
    target_id: str | None = Field(default=None, alias="targetId")
    parameters: dict
    summary: str = Field(min_length=1, max_length=1000)
    risk_level: str = Field(alias="riskLevel")
    run_id: str | None = Field(default=None, alias="runId")
    ttl_seconds: int = Field(default=900, alias="ttlSeconds", ge=1, le=3600)
    idempotency_seed: str = Field(
        default="",
        alias="idempotencySeed",
        max_length=128,
    )


class ApproveActionRequest(BaseModel):
    payload: dict


class RejectActionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
