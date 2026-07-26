"""多智能体运行时：预算、取消、身份上下文与工具调用中间件。"""
from dataclasses import dataclass, field
from time import monotonic

from langchain.agents.middleware import wrap_tool_call

from ..models import User
from .contracts import (
    AGENT_BUDGET_EXCEEDED,
    AGENT_RUN_CANCELLED,
    ActorContext,
)


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
    """生产运行使用的固定安全预算。"""
    return RunBudget(max_nodes=8, max_tool_calls=12, timeout_seconds=45)


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
    """在每次真实工具执行前消费当前 RunBudget。"""
    context = request.runtime.context
    budget = getattr(context, "budget", None)
    if budget is not None:
        budget.consume_tool_call()
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
