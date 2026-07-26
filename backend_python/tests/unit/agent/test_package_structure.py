"""Target public imports for the flattened Agent package layout."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("module_name", "public_name"),
    [
        ("app.agent.service", "stream_chat_events"),
        ("app.agent.runtime", "RunBudget"),
        ("app.agent.gateway", "ModelGateway"),
        ("app.agent.registry", "AgentRegistry"),
        ("app.agent.supervisors.teacher", "build_teacher_supervisor"),
        ("app.agent.subagents.teacher_data", "build_teacher_data_agent"),
        ("app.agent.graphs.teacher", "build_teacher_graph"),
        ("app.agent.tools.common", "TeacherContext"),
        ("app.agent.tools.teacher", "STRUCTURED_TOOLS"),
    ],
)
def test_target_agent_package_exposes_public_imports(module_name, public_name):
    module = import_module(module_name)

    assert hasattr(module, public_name), (
        f"{module_name} must publicly expose {public_name}"
    )
