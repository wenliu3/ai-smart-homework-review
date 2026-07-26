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


def query_audit_metrics(db: Session) -> AdminQueryResult:
    """OperationLog 聚合审计（规划 5.3）：只出计数与端点频次，绝不出描述正文。"""
    from ...models import OperationLog

    total = db.query(func.count(OperationLog.id)).scalar() or 0
    login_failures = (
        db.query(func.count(OperationLog.id))
        .filter(
            OperationLog.endpoint.like("%/auth/login%"),
            OperationLog.status_code >= 400,
        )
        .scalar()
        or 0
    )
    denied = (
        db.query(func.count(OperationLog.id))
        .filter(OperationLog.status_code == 403)
        .scalar()
        or 0
    )
    top_rows = (
        db.query(OperationLog.endpoint, func.count(OperationLog.id))
        .group_by(OperationLog.endpoint)
        .order_by(func.count(OperationLog.id).desc())
        .limit(10)
        .all()
    )
    return AdminQueryResult(
        status="ok",
        title="操作日志聚合审计",
        metrics={
            "operationCount": total,
            "loginFailureCount": login_failures,
            "permissionDeniedCount": denied,
        },
        records=[
            {"endpoint": endpoint or "unknown", "count": count}
            for endpoint, count in top_rows
        ],
        evidence_refs=["mysql://operation_logs?fields=aggregate_only"],
        limitations=[
            "操作日志仅覆盖写操作与登录端点，GET 请求的权限拒绝不入日志",
        ],
    )


def query_activity_metrics(db: Session) -> AdminQueryResult:
    """活跃度与班级规模统计（规划 5.3）。"""
    from datetime import timedelta

    from ...core.utils import now
    from ...models import Class, ClassStudent

    active_classes = (
        db.query(Class).filter(Class.status == "active").all()
    )
    class_ids = [item.id for item in active_classes]
    member_count = (
        db.query(func.count(ClassStudent.id))
        .filter(
            ClassStudent.class_id.in_(class_ids) if class_ids else False,
            ClassStudent.status == "active",
        )
        .scalar()
        or 0
    ) if class_ids else 0
    week_ago = now() - timedelta(days=7)
    recent_submissions = (
        db.query(func.count(Submission.id))
        .filter(Submission.submitted_at >= week_ago)
        .scalar()
        or 0
    )
    class_count = len(class_ids)
    return AdminQueryResult(
        status="ok",
        title="平台活跃度与班级规模",
        metrics={
            "activeClassCount": class_count,
            "avgClassSize": (
                round(member_count / class_count, 1) if class_count else 0.0
            ),
            "recentSubmissionCount": recent_submissions,
        },
        evidence_refs=["mysql://classes+submissions/aggregate"],
    )


def query_model_connectivity(db: Session) -> AdminQueryResult:
    """逐个探测 active 模型连通性（规划 5.3）；结果只含脱敏元数据。"""
    from ...crud import ai_model as ai_model_crud

    models = db.query(AiModel).filter(AiModel.status == "active").all()
    records = []
    for model in models:
        try:
            probe = ai_model_crud.test_connection(db, model.code)
        except Exception:
            probe = {"success": False, "responseTime": 0, "message": "探测失败"}
        records.append({
            "code": model.code,
            "name": model.name,
            "reachable": bool(probe.get("success")),
            "responseTimeMs": probe.get("responseTime", 0),
            "message": str(probe.get("message", ""))[:200],
        })
    return AdminQueryResult(
        status="ok" if records else "empty",
        title="模型连通性探测",
        metrics={
            "probedCount": len(records),
            "reachableCount": sum(1 for r in records if r["reachable"]),
        },
        records=records,
        evidence_refs=["mysql://ai_models/connectivity_probe"],
        limitations=["探测为实时请求，结果反映探测时刻的可达性"],
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


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_audit_metrics(runtime: ToolRuntime[AdminContext]) -> dict:
    """查询操作日志聚合审计指标（登录失败/权限拒绝/端点频次），不返回日志正文。"""
    with SessionLocal() as db:
        return query_audit_metrics(db).model_dump(mode="json")


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_activity_metrics(runtime: ToolRuntime[AdminContext]) -> dict:
    """查询平台活跃度与班级规模聚合统计。"""
    with SessionLocal() as db:
        return query_activity_metrics(db).model_dump(mode="json")


@tool(parse_docstring=True, error_on_invalid_docstring=False)
@_safe_tool
def get_model_connectivity(runtime: ToolRuntime[AdminContext]) -> dict:
    """探测各 active 模型的连通性与响应时间，不返回任何密钥。"""
    with SessionLocal() as db:
        return query_model_connectivity(db).model_dump(mode="json")


ADMIN_TOOLS = [
    get_platform_operations,
    get_agent_runtime_metrics,
    get_model_governance_metrics,
    get_audit_metrics,
    get_activity_metrics,
    get_model_connectivity,
]

__all__ = [
    "ADMIN_TOOLS",
    "AdminContext",
    "AdminQueryResult",
    "query_agent_runtime_metrics",
    "query_model_governance_metrics",
    "query_platform_operations",
]
