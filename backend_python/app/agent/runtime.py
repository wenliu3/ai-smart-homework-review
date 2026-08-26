"""多智能体运行时：预算、取消、身份上下文与工具调用中间件。"""
import logging
from dataclasses import dataclass, field
from time import monotonic

from langchain.agents.middleware import wrap_tool_call

from ..config import settings
from ..models import User
from .contracts import (
    AGENT_BUDGET_EXCEEDED,
    AGENT_RUN_CANCELLED,
    ActorContext,
)

logger = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    code = AGENT_BUDGET_EXCEEDED


class RunCancelled(RuntimeError):
    code = AGENT_RUN_CANCELLED


@dataclass
class RunBudget:
    max_nodes: int = 8
    max_tool_calls: int = 12
    # 模型调用次数上限（每次 agent.invoke 记一次；含格式修复重试）
    max_model_calls: int = 12
    timeout_seconds: int = 45
    node_count: int = 0
    tool_call_count: int = 0
    model_call_count: int = 0
    started_at: float = field(default_factory=monotonic)

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.timeout_seconds - (monotonic() - self.started_at))

    def consume_node(self) -> None:
        self.node_count += 1
        self._validate()

    def consume_tool_call(self) -> None:
        self.tool_call_count += 1
        self._validate()

    def consume_model_call(self) -> None:
        self.model_call_count += 1
        self._validate()

    def _validate(self) -> None:
        if self.node_count > self.max_nodes:
            raise BudgetExceeded("Agent 节点数超过限制")
        if self.tool_call_count > self.max_tool_calls:
            raise BudgetExceeded("工具调用次数超过限制")
        if self.model_call_count > self.max_model_calls:
            raise BudgetExceeded("模型调用次数超过限制")
        if monotonic() - self.started_at > self.timeout_seconds:
            raise BudgetExceeded("Agent 运行超时")


def is_model_timeout(exc: BaseException) -> bool:
    """判断异常是否属于模型调用超时族（规划 4.2）。

    覆盖 openai.APITimeoutError 与 httpx 超时族；供编排层把超时
    映射为稳定错误码 AGENT_MODEL_TIMEOUT，与普通模型错误区分。
    """
    try:
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            return True
    except ImportError:  # pragma: no cover
        pass
    try:
        import openai

        if isinstance(exc, openai.APITimeoutError):
            return True
    except ImportError:  # pragma: no cover
        pass
    return False


def default_run_budget() -> RunBudget:
    """教师/学生/管理员助手的整轮安全预算。

    timeout_seconds 从配置读取（AGENT_RUN_TIMEOUT_SECONDS，默认 150），因为创建
    作业草稿等写操作路径是「多次模型调用串行执行」——单次模型超时远小于整轮预算，
    但多条串行累计会超过旧的固定 45s。批改任务用独立的 grading_run_budget()，
    不受此默认值影响。
    """
    return RunBudget(
        max_nodes=8,
        max_tool_calls=12,
        max_model_calls=12,
        timeout_seconds=settings.AGENT_RUN_TIMEOUT_SECONDS,
    )


def grading_run_budget() -> RunBudget:
    """批改任务预算（规格 §15.2）：模型调用 ≤6 次、任务 ≤120s。

    与 celery 任务的 soft_time_limit=120 对齐——预算先于软超时触发时
    走结构化降级（转人工），而不是被 SoftTimeLimitExceeded 打断。
    """
    return RunBudget(
        max_nodes=8,
        max_tool_calls=12,
        max_model_calls=6,
        timeout_seconds=120,
    )


def build_actor_context(user: User, request_id: str, session_id: str) -> ActorContext:
    """从已认证用户构造只读 ActorContext。"""
    return ActorContext(
        user_id=user.id,
        role=user.role,
        request_id=request_id,
        session_id=session_id,
    )


@wrap_tool_call
def tool_budget_middleware(request, handler):
    """在每次真实工具执行前消费当前 RunBudget，并记录工具名/参数键。

    参数只记录键名（arg_keys），不记录值，避免把班级名/学生名等业务数据打进日志。
    用于排查「一次性调用太多工具」时到底是哪个工具、带什么参数被反复调用。
    """
    context = request.runtime.context
    budget = getattr(context, "budget", None)

    tool_call = getattr(request, "tool_call", None) or {}
    tool_name = tool_call.get("name", "unknown")
    args = tool_call.get("args")
    arg_keys = sorted(args.keys()) if isinstance(args, dict) else []

    if budget is not None:
        logger.warning(
            "Agent tool call: name=%s count=%d/%d arg_keys=%s",
            tool_name,
            budget.tool_call_count + 1,
            budget.max_tool_calls,
            arg_keys,
        )
        budget.consume_tool_call()
    else:
        logger.warning(
            "Agent tool call(no-budget): name=%s arg_keys=%s",
            tool_name,
            arg_keys,
        )

    return handler(request)


__all__ = [
    "BudgetExceeded",
    "RunBudget",
    "RunCancelled",
    "build_actor_context",
    "default_run_budget",
    "grading_run_budget",
    "is_model_timeout",
    "tool_budget_middleware",
]
