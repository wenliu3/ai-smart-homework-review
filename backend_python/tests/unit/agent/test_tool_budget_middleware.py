"""LangChain v1 工具 middleware 必须消费每次真实工具调用预算。"""

from types import SimpleNamespace

import pytest

from app.agent.runtime import BudgetExceeded, RunBudget, tool_budget_middleware
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
