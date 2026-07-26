"""新版多智能体工具必须返回结构化对象。"""

from langchain.tools import ToolRuntime

from app.agent.runtime import RunBudget
from app.agent.tools.common import TeacherContext
from app.agent.tools.teacher import STRUCTURED_TOOLS, serialize_result
from app.agent.tools.teacher import TeachingQueryResult


def test_serialize_result_preserves_metrics_records_and_evidence():
    result = TeachingQueryResult(
        status="ok",
        title="班级列表",
        metrics={"classCount": 1},
        records=[{"name": "一班"}],
        evidence_refs=["mysql://classes?scope=current_teacher"],
    )

    payload = serialize_result(result)

    assert payload["status"] == "ok"
    assert payload["metrics"] == {"classCount": 1}
    assert payload["records"] == [{"name": "一班"}]
    assert payload["evidence_refs"] == ["mysql://classes?scope=current_teacher"]


def test_all_structured_tool_input_schemas_are_fully_defined():
    """LangChain 必须能在实际工具调用前构建每个工具的 Pydantic Schema。"""
    runtime = ToolRuntime(
        state={},
        context=TeacherContext(teacher_id=7, budget=RunBudget()),
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-test",
        store=None,
    )
    for structured_tool in STRUCTURED_TOOLS:
        public_schema = structured_tool.tool_call_schema.model_json_schema()
        assert isinstance(public_schema, dict)
        payload = {"runtime": runtime}
        for field_name, field in structured_tool.args_schema.model_fields.items():
            if field_name == "runtime":
                continue
            payload[field_name] = 1 if field.annotation is int else "test"
        validated = structured_tool.args_schema.model_validate(payload)
        assert validated.runtime.context.teacher_id == 7
