"""LangChain v1 工具 middleware 必须消费每次真实工具调用预算。"""

from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import patch

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agent.registry import GLOBAL_RUN_TOOL_LIMIT
from app.agent.runtime import (
    BudgetExceeded,
    RunBudget,
    model_budget_middleware,
    tool_budget_middleware,
)
from app.agent.tools.common import TeacherContext


def test_tool_budget_middleware_rejects_thirteenth_call():
    context = TeacherContext(
        teacher_id=7,
        budget=RunBudget(max_tool_calls=12),
    )
    request = SimpleNamespace(runtime=SimpleNamespace(context=context))

    for _ in range(12):
        assert tool_budget_middleware.wrap_tool_call(
            request, lambda req: "ok",
        ) == "ok"

    with pytest.raises(BudgetExceeded):
        tool_budget_middleware.wrap_tool_call(request, lambda req: "never")


def test_tool_budget_middleware_logs_tool_name_and_arg_keys():
    """诊断日志记录工具名与参数键（不含参数值），便于定位哪个工具被反复调用。"""
    log = SimpleNamespace(runtime=SimpleNamespace(
        context=TeacherContext(teacher_id=7, budget=RunBudget(max_tool_calls=20)),
    ))
    log.tool_call = {
        "name": "get_my_classes",
        "args": {"class_id": 7, "include_students": True},
    }

    with patch("app.agent.runtime.logger.warning") as mock_warning:
        assert tool_budget_middleware.wrap_tool_call(
            log, lambda req: "ok",
        ) == "ok"

    call_kwargs = mock_warning.call_args.kwargs
    assert mock_warning.call_args.args[0] == "Agent tool call: name=%s count=%d/%d arg_keys=%s"
    assert mock_warning.call_args.args[1:] == ("get_my_classes", 1, 20, ["class_id", "include_students"])
    assert "7" not in str(call_kwargs) and 7 not in mock_warning.call_args.args  # 不记录参数值


def test_model_budget_middleware_counts_each_real_model_call():
    """模型预算按「每次真实模型请求」计数，而非 agent.invoke 外层一次。"""
    budget = RunBudget()
    request = SimpleNamespace(runtime=SimpleNamespace(
        context=TeacherContext(teacher_id=7, budget=budget),
    ))

    model_budget_middleware.wrap_model_call(request, lambda req: "ok")
    model_budget_middleware.wrap_model_call(request, lambda req: "ok")

    assert budget.model_call_count == 2


def test_model_budget_middleware_respects_max_model_calls():
    budget = RunBudget(max_model_calls=1)
    request = SimpleNamespace(runtime=SimpleNamespace(
        context=TeacherContext(teacher_id=7, budget=budget),
    ))
    model_budget_middleware.wrap_model_call(request, lambda req: "ok")
    with pytest.raises(BudgetExceeded):
        model_budget_middleware.wrap_model_call(request, lambda req: "ok")


@tool
def _probe_tool(x: int = 1) -> str:
    """Probe tool."""
    return "ok"


class _ManyToolCallsModel(BaseChatModel):
    """依次返回 N 次同一工具调用，最后返回最终回答。"""

    steps: List[BaseMessage]

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self.steps.pop(0))])

    @property
    def _llm_type(self) -> str:
        return "many-tool-calls"


def test_global_tool_limit_blocks_before_budget_is_consumed():
    """被全局工具上限拦截的调用不能错误消耗工具预算（§7 顺序保证）。"""
    tool_call = {
        "name": "probe_tool",
        "args": {"x": 1},
        "id": "c1",
        "type": "tool_call",
    }
    model = _ManyToolCallsModel(steps=(
        [AIMessage(content="", tool_calls=[tool_call]) for _ in range(8)]
        + [AIMessage(content="done")]
    ))
    budget = RunBudget()
    agent = create_agent(
        model=model,
        tools=[_probe_tool],
        context_schema=TeacherContext,
        middleware=[
            ToolCallLimitMiddleware(run_limit=3, exit_behavior="continue"),
            tool_budget_middleware,
        ],
    )

    agent.invoke({"messages": []}, context=TeacherContext(
        teacher_id=7, budget=budget,
    ))

    # 只允许 3 次真实执行；被拦截的 5 次不消耗工具预算
    assert budget.tool_call_count == 3


def test_global_run_tool_limit_constant_is_bounded():
    """全局单轮工具上限必须显著低于模型/工具预算，作为探索闸门。"""
    budget = RunBudget()
    assert GLOBAL_RUN_TOOL_LIMIT < budget.max_model_calls
    assert GLOBAL_RUN_TOOL_LIMIT < budget.max_tool_calls
