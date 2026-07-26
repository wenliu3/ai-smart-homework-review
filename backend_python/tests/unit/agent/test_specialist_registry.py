"""专业 Agent 注册表测试（任务 2）。

验证三个真实 specialist Agent 的配置隔离和缓存行为。
全部使用假 ChatModel / agent_factory，不访问外部 API。

核心断言：
- 三个 Agent 名称、Prompt 版本、模型 Profile 互不相同。
- 数据和策略 Agent 持有只读工具；审核 Agent 工具列表为空。
- SpecialistRegistry 按 (agent_name, model_cache_key, prompt_version) 缓存。
- ActorContext 不出现在任何工具的参数 Schema 中。
"""
from unittest.mock import MagicMock

from app.agent.contracts import ActorContext, ModelProfile
from app.agent.runtime import build_actor_context
from app.agent.registry import SpecialistRegistry, SpecialistSpec
from app.agent.tools.common import ALL_TOOLS, TeacherContext
from app.models import User


# ========== Agent 配置隔离 ==========

def test_registered_specialists_have_distinct_names():
    """所有已接线 specialist 名称互不相同。"""
    specs = SpecialistRegistry.default_specs()
    names = {spec.name for spec in specs}
    assert names == {
        "teaching_data",
        "teaching_strategy",
        "final_reviewer",
        "grading",
        "grading_review",
        "plagiarism_analysis",
        "learning_coach",
        "feedback_explainer",
        "learning_planner",
        "student_final_reviewer",
        "operations_analysis",
        "audit_analysis",
        "model_governance",
        "admin_final_reviewer",
    }


def test_data_and_strategy_use_general_profile_reviewer_uses_reviewer_profile():
    """数据与策略使用 general Profile，审核使用 reviewer Profile。"""
    specs = {spec.name: spec for spec in SpecialistRegistry.default_specs()}
    assert specs["teaching_data"].profile == ModelProfile.GENERAL
    assert specs["teaching_strategy"].profile == ModelProfile.GENERAL
    assert specs["final_reviewer"].profile == ModelProfile.REVIEWER


def test_all_specialists_have_distinct_prompt_names():
    """所有 specialist 使用互不混淆的 Prompt 名称。"""
    specs = {spec.name: spec for spec in SpecialistRegistry.default_specs()}
    versions = {spec.prompt_name for spec in specs.values()}
    assert len(versions) == 14
    assert "teacher_data_specialist" in versions
    assert "teacher_strategy_specialist" in versions
    assert "teacher_final_reviewer" in versions


# ========== 工具隔离 ==========

def test_data_and_strategy_have_readonly_tools():
    """数据和策略 Agent 持有只读工具。"""
    specs = {spec.name: spec for spec in SpecialistRegistry.default_specs()}
    assert len(specs["teaching_data"].tools) > 0
    assert len(specs["teaching_strategy"].tools) > 0
    # 所有工具都是只读的（名称以 get_ 开头）
    for tool in specs["teaching_data"].tools:
        assert tool.name.startswith("get_")
    for tool in specs["teaching_strategy"].tools:
        assert tool.name.startswith("get_")


def test_reviewer_has_empty_tools():
    """审核 Agent 工具列表为空，防止审核者自行查数据。"""
    specs = {spec.name: spec for spec in SpecialistRegistry.default_specs()}
    assert specs["final_reviewer"].tools == ()
    assert specs["grading"].tools == ()
    assert specs["grading_review"].tools == ()
    assert specs["plagiarism_analysis"].tools == ()
    assert len(specs["learning_coach"].tools) > 0
    assert len(specs["feedback_explainer"].tools) > 0
    assert len(specs["learning_planner"].tools) > 0
    assert specs["student_final_reviewer"].tools == ()
    assert len(specs["operations_analysis"].tools) > 0
    assert len(specs["audit_analysis"].tools) > 0
    assert len(specs["model_governance"].tools) > 0
    assert specs["admin_final_reviewer"].tools == ()


# ========== 缓存行为 ==========

def test_registry_caches_by_agent_name_model_key_prompt_version(db, ai_model_factory):
    """相同 (agent_name, model_cache_key, prompt_version) 返回同一 Agent 实例。"""
    ai_model_factory()
    factory_calls = []

    def fake_agent_factory(
        model, tools, system_prompt, context_schema, response_format=None, middleware=None,
    ):
        agent = MagicMock(name=f"agent_{len(factory_calls)}")
        factory_calls.append(agent)
        return agent

    registry = SpecialistRegistry(agent_factory=fake_agent_factory)
    agent1 = registry.get_specialist("teaching_data", db)
    agent2 = registry.get_specialist("teaching_data", db)

    assert agent1 is agent2
    assert len(factory_calls) == 1  # 第二次命中缓存


def test_registry_rebuilds_when_model_config_changes(db, ai_model_factory):
    """模型配置变更后缓存失效，重建 Agent。"""
    from datetime import datetime, timedelta

    model = ai_model_factory()
    factory_calls = []

    def fake_agent_factory(
        model, tools, system_prompt, context_schema, response_format=None, middleware=None,
    ):
        agent = MagicMock(name=f"agent_{len(factory_calls)}")
        factory_calls.append(agent)
        return agent

    registry = SpecialistRegistry(agent_factory=fake_agent_factory)
    agent1 = registry.get_specialist("teaching_data", db)

    # 模拟管理员修改模型配置（updated_at 变化）
    model.updated_at = datetime.now() + timedelta(seconds=1)
    db.commit()

    agent2 = registry.get_specialist("teaching_data", db)
    assert agent1 is not agent2
    assert len(factory_calls) == 2


def test_registry_returns_different_instances_for_different_specialists(db, ai_model_factory):
    """不同 specialist 返回不同 Agent 实例。"""
    ai_model_factory()
    factory_calls = []

    def fake_agent_factory(
        model, tools, system_prompt, context_schema, response_format=None, middleware=None,
    ):
        agent = MagicMock(name=f"agent_{len(factory_calls)}")
        factory_calls.append(agent)
        return agent

    registry = SpecialistRegistry(agent_factory=fake_agent_factory)
    data_agent = registry.get_specialist("teaching_data", db)
    strategy_agent = registry.get_specialist("teaching_strategy", db)
    reviewer_agent = registry.get_specialist("final_reviewer", db)

    assert data_agent is not strategy_agent
    assert data_agent is not reviewer_agent
    assert strategy_agent is not reviewer_agent
    assert len(factory_calls) == 3


# ========== Agent 构建参数 ==========

def test_agent_factory_receives_correct_tools_per_specialist(db, ai_model_factory):
    """agent_factory 收到的 tools 与 spec 一致。"""
    ai_model_factory()
    received_tools = {}

    def recording_agent_factory(
        model, tools, system_prompt, context_schema, response_format=None, middleware=None,
    ):
        agent = MagicMock()
        received_tools[system_prompt[:20]] = list(tools)
        return agent

    registry = SpecialistRegistry(agent_factory=recording_agent_factory)
    registry.get_specialist("teaching_data", db)
    registry.get_specialist("teaching_strategy", db)
    registry.get_specialist("final_reviewer", db)

    all_tool_counts = [len(t) for t in received_tools.values()]
    # 数据和策略有工具，审核无工具
    assert any(c > 0 for c in all_tool_counts)
    assert 0 in all_tool_counts  # final_reviewer


def test_agent_factory_receives_context_schema(db, ai_model_factory):
    """agent_factory 收到 context_schema=TeacherContext，保证身份注入。"""
    ai_model_factory()
    received_contexts = []

    def recording_agent_factory(
        model, tools, system_prompt, context_schema, response_format=None, middleware=None,
    ):
        received_contexts.append(context_schema)
        return MagicMock()

    registry = SpecialistRegistry(agent_factory=recording_agent_factory)
    registry.get_specialist("teaching_data", db)

    assert received_contexts[0] is TeacherContext


def test_agent_factory_receives_structured_response_schema(db, ai_model_factory):
    """新版 create_agent 必须为全部 specialist 配置 Pydantic response_format。"""
    from app.agent.contracts import (
        GradingDraft,
        PlagiarismExplanation,
        ModelGovernanceResponse,
        ReviewResult,
        SpecialistResponse,
    )

    ai_model_factory()
    received_formats = []

    def recording_agent_factory(
        model, tools, system_prompt, context_schema, response_format=None, middleware=None,
    ):
        received_formats.append(response_format)
        return MagicMock()

    registry = SpecialistRegistry(agent_factory=recording_agent_factory)
    registry.get_specialist("teaching_data", db)
    registry.get_specialist("teaching_strategy", db)
    registry.get_specialist("final_reviewer", db)
    registry.get_specialist("grading", db)
    registry.get_specialist("grading_review", db)
    registry.get_specialist("plagiarism_analysis", db)
    registry.get_specialist("learning_coach", db)
    registry.get_specialist("feedback_explainer", db)
    registry.get_specialist("learning_planner", db)
    registry.get_specialist("student_final_reviewer", db)
    registry.get_specialist("operations_analysis", db)
    registry.get_specialist("audit_analysis", db)
    registry.get_specialist("model_governance", db)
    registry.get_specialist("admin_final_reviewer", db)

    assert received_formats == [
        SpecialistResponse,
        SpecialistResponse,
        ReviewResult,
        GradingDraft,
        GradingDraft,
        PlagiarismExplanation,
        SpecialistResponse,
        SpecialistResponse,
        SpecialistResponse,
        ReviewResult,
        SpecialistResponse,
        SpecialistResponse,
        ModelGovernanceResponse,
        ReviewResult,
    ]


# ========== ActorContext 服务端身份构造器 ==========

def test_build_actor_context_from_user():
    """从认证用户构造 ActorContext，字段完整。"""
    user = User(id=42, username="t_alice", role="teacher", status="active")
    ctx = build_actor_context(user=user, request_id="req-001", session_id="sess-001")
    assert ctx.user_id == 42
    assert ctx.role == "teacher"
    assert ctx.request_id == "req-001"
    assert ctx.session_id == "sess-001"


def test_actor_context_fields_not_in_tool_schema():
    """ActorContext 的 user_id / role / request_id / session_id 不出现在任何工具参数 Schema 中。"""
    sensitive = {"user_id", "role", "request_id", "session_id", "teacher_id", "student_id"}
    for tool in ALL_TOOLS:
        schema = tool.args_schema
        if schema is None:
            continue
        fields = set(schema.model_fields.keys())
        leaked = sensitive & fields
        assert not leaked, f"工具 {tool.name} 的参数 Schema 泄露了身份字段: {leaked}"


def test_actor_context_rejects_missing_fields():
    """ActorContext 必须包含所有必需字段（防止身份伪造）。"""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ActorContext(user_id=1, role="teacher")  # 缺少 request_id 和 session_id
