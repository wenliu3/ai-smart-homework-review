"""管理员聚合只读工具：永不返回聊天正文、作业正文或模型密钥。"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Literal

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...assistant_database import AssistantSessionLocal
from ...database import SessionLocal
from ...models import AgentRun, AiModel, Assignment, Submission, User
from ..runtime import RunBudget


class AdminQueryResult(BaseModel):
    status: Literal["ok", "empty", "error"]
    title: str
    metrics: dict = Field(default_factory=dict)
    records: list[dict] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass
class AdminContext:
    admin_id: int
    budget: RunBudget | None = None


def query_platform_operations(db: Session) -> AdminQueryResult:
    role_counts = dict(
        db.query(User.role, func.count(User.id)).group_by(User.role).all()
    )
    metrics = {
        "userCount": sum(role_counts.values()),
        "teacherCount": role_counts.get("teacher", 0),
        "studentCount": role_counts.get("student", 0),
        "assignmentCount": db.query(func.count(Assignment.id)).filter(Assignment.alive()).scalar() or 0,
        "submissionCount": db.query(func.count(Submission.id)).scalar() or 0,
    }
    return AdminQueryResult(
        status="ok",
        title="平台聚合运营指标",
        metrics=metrics,
        evidence_refs=["mysql://platform/aggregate"],
    )


def query_model_governance_metrics(db: Session) -> AdminQueryResult:
    models = db.query(AiModel).order_by(AiModel.code.asc()).all()
    records = [
        {
            "code": item.code,
            "name": item.name,
            "provider": item.provider,
            "modelName": item.model_name,
            "status": item.status,
            "isDefault": bool(item.is_default),
            "totalUsage": item.total_usage or 0,
            "totalTokens": item.total_tokens or 0,
            "lastUsedAt": (
                item.last_used_at.isoformat()
                if item.last_used_at
                else None
            ),
        }
        for item in models
    ]
    return AdminQueryResult(
        status="ok" if records else "empty",
        title="模型治理指标",
        metrics={
            "modelCount": len(records),
            "activeModelCount": sum(
                1 for item in records if item["status"] == "active"
            ),
            "totalUsage": sum(item["totalUsage"] for item in records),
            "totalTokens": sum(item["totalTokens"] for item in records),
        },
        records=records,
        evidence_refs=["mysql://ai_models?fields=aggregate_safe"],
    )


def query_agent_runtime_metrics(db: Session) -> AdminQueryResult:
    status_counts = dict(
        db.query(AgentRun.status, func.count(AgentRun.id))
        .group_by(AgentRun.status)
        .all()
    )
    intent_counts = dict(
        db.query(AgentRun.intent, func.count(AgentRun.id))
        .group_by(AgentRun.intent)
        .all()
    )
    return AdminQueryResult(
        status="ok",
        title="Agent 脱敏运行指标",
        metrics={
            "runCount": sum(status_counts.values()),
            "statusCounts": status_counts,
            "intentCounts": intent_counts,
        },
        evidence_refs=["postgresql://agent_runs?fields=aggregate_only"],
    )


def _safe_tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return AdminQueryResult(
                status="error",
                title="聚合查询失败",
                limitations=["查询暂时失败，请稍后重试"],
            ).model_dump(mode="json")

    return wrapper


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_platform_operations(
    runtime: ToolRuntime[AdminContext],
) -> dict:
    """查询平台用户、作业和提交的聚合运营指标，不返回任何正文。"""
    with SessionLocal() as db:
        return query_platform_operations(db).model_dump(mode="json")


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_agent_runtime_metrics(
    runtime: ToolRuntime[AdminContext],
) -> dict:
    """查询 Agent 运行状态和意图的脱敏聚合指标，不返回消息或最终回答。"""
    with AssistantSessionLocal() as db:
        return query_agent_runtime_metrics(db).model_dump(mode="json")


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_model_governance_metrics(
    runtime: ToolRuntime[AdminContext],
) -> dict:
    """查询无密钥的模型状态、用量和 Token 聚合指标。"""
    with SessionLocal() as db:
        return query_model_governance_metrics(db).model_dump(mode="json")


ADMIN_TOOLS = [
    get_platform_operations,
    get_agent_runtime_metrics,
    get_model_governance_metrics,
]

__all__ = [
    "ADMIN_TOOLS",
    "AdminContext",
    "AdminQueryResult",
    "query_agent_runtime_metrics",
    "query_model_governance_metrics",
    "query_platform_operations",
]
