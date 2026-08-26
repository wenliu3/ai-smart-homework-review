"""LangChain v1 工具 middleware 必须消费每次真实工具调用预算。"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agent.runtime import (
    BudgetExceeded,
    RunBudget,
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
