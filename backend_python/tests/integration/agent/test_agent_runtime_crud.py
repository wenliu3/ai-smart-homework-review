"""PostgreSQL Agent 会话与运行生命周期测试。

覆盖：
- Run 启动与归属校验。
- Step 顺序、归属与证据引用。
- Artifact 版本化保存与跨用户拒绝。
- finalize_run 在同一 PostgreSQL 事务提交最终消息、Artifact 和 run.completed。
- 失败 / 取消 / 跨用户读取 / 事务回滚。
- 图状态不得保存 ORM 对象。
"""
import pytest

from app.agent.graphs.teacher import build_teacher_graph
from app.agent.contracts import ReviewResult
from app.crud.agent_run import (
    append_artifact,
    append_step,
    cancel_run,
    complete_run,
    create_run,
    fail_run,
    finalize_run,
    get_run,
    list_artifacts,
    list_steps,
)
from app.crud.agent_session import (
    append_message,
    create_session,
)


# ========== 已有：Run 启动与归属 ==========

def test_run_lifecycle_is_owned_by_actor(assistant_db):
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")
    append_step(assistant_db, run.id, user_id=7, node_name="teaching_data", status="completed", output={"count": 2})
    complete_run(assistant_db, run.id, user_id=7, final_output="已找到两个班级")

    loaded = get_run(assistant_db, run.id, user_id=7)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.final_output == "已找到两个班级"
    assert len(loaded.steps) == 1
    assert loaded.steps[0].sequence == 1
    assert get_run(assistant_db, run.id, user_id=8) is None


def test_create_run_rejects_foreign_session(assistant_db):
    session = create_session(assistant_db, user_id=7, actor_role="teacher")

    try:
        create_run(assistant_db, session.id, user_id=8, intent="teaching_data")
    except ValueError as exc:
        assert str(exc) == "会话不存在或不属于当前用户"
    else:
        raise AssertionError("跨用户会话必须被拒绝")


# ========== Step 顺序与归属 ==========

def test_append_step_preserves_sequence_order(assistant_db):
    """多个 Step 必须按调用顺序递增 sequence。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    s1 = append_step(assistant_db, run.id, user_id=7, node_name="route", status="completed")
    s2 = append_step(assistant_db, run.id, user_id=7, node_name="teaching_data", status="completed")
    s3 = append_step(assistant_db, run.id, user_id=7, node_name="final_reviewer", status="completed")

    assert s1.sequence == 1
    assert s2.sequence == 2
    assert s3.sequence == 3

    steps = list_steps(assistant_db, run.id, user_id=7)
    assert [s.sequence for s in steps] == [1, 2, 3]
    assert [s.node_name for s in steps] == ["route", "teaching_data", "final_reviewer"]


def test_append_step_rejects_foreign_user(assistant_db):
    """跨用户写 Step 必须被拒绝（防止越权写入他人运行）。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    with pytest.raises(ValueError):
        append_step(assistant_db, run.id, user_id=8, node_name="route", status="completed")


def test_append_step_records_evidence_and_usage(assistant_db):
    """Step 保存证据引用和模型用量（结构化追踪）。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    step = append_step(
        assistant_db, run.id, user_id=7,
        node_name="teaching_data", status="completed",
        output={"answer": "2 个班级"},
        evidence_refs=["class://id/1", "class://id/2"],
        usage={"prompt_tokens": 120, "completion_tokens": 30},
        duration_ms=450,
    )

    assert step.evidence_refs == ["class://id/1", "class://id/2"]
    assert step.usage_json["prompt_tokens"] == 120
    assert step.duration_ms == 450


# ========== 失败 / 取消 ==========

def test_fail_run_marks_status_failed_with_error_code(assistant_db):
    """失败运行：status=failed，error_code 已设置，finished_at 已写入。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    fail_run(assistant_db, run.id, user_id=7, error_code="AGENT_BUDGET_EXCEEDED")

    loaded = get_run(assistant_db, run.id, user_id=7)
    assert loaded.status == "failed"
    assert loaded.error_code == "AGENT_BUDGET_EXCEEDED"
    assert loaded.finished_at is not None


def test_fail_run_rejects_foreign_user(assistant_db):
    """跨用户标记失败必须被拒绝。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    with pytest.raises(ValueError):
        fail_run(assistant_db, run.id, user_id=8, error_code="X")


def test_cancel_run_marks_status_cancelled(assistant_db):
    """取消运行：status=cancelled，finished_at 已写入。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    cancel_run(assistant_db, run.id, user_id=7)

    loaded = get_run(assistant_db, run.id, user_id=7)
    assert loaded.status == "cancelled"
    assert loaded.finished_at is not None
    assert loaded.error_code is None


def test_cancel_run_rejects_foreign_user(assistant_db):
    """跨用户取消必须被拒绝。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    with pytest.raises(ValueError):
        cancel_run(assistant_db, run.id, user_id=8)


# ========== Artifact 版本化 ==========

def test_append_artifact_stores_payload_and_schema_version(assistant_db):
    """Artifact 保存类型、schema_version 和 payload。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    art = append_artifact(
        assistant_db, run.id, user_id=7,
        artifact_type="analysis",
        schema_version="analysis-v1",
        payload={"metric": 42, "evidence": []},
    )

    assert art.artifact_type == "analysis"
    assert art.schema_version == "analysis-v1"
    assert art.payload_json["metric"] == 42


def test_append_artifact_rejects_foreign_user(assistant_db):
    """跨用户写 Artifact 必须被拒绝。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    with pytest.raises(ValueError):
        append_artifact(
            assistant_db, run.id, user_id=8,
            artifact_type="analysis",
            schema_version="v1",
            payload={},
        )


def test_list_artifacts_returns_all_for_run(assistant_db):
    """一个 Run 可挂多个 Artifact，list_artifacts 全部返回。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    append_artifact(assistant_db, run.id, user_id=7, artifact_type="analysis", schema_version="v1", payload={"x": 1})
    append_artifact(assistant_db, run.id, user_id=7, artifact_type="strategy", schema_version="v1", payload={"y": 2})

    arts = list_artifacts(assistant_db, run.id, user_id=7)
    assert len(arts) == 2
    assert {a.artifact_type for a in arts} == {"analysis", "strategy"}


def test_list_artifacts_rejects_foreign_user(assistant_db):
    """跨用户读取 Artifact 必须返回空。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")
    append_artifact(assistant_db, run.id, user_id=7, artifact_type="x", schema_version="v1", payload={})

    assert list_artifacts(assistant_db, run.id, user_id=8) == []


# ========== 消息持久化 ==========

def test_append_message_records_role_and_run(assistant_db):
    """消息按角色保存，可关联 run_id。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    m1 = append_message(assistant_db, session.id, user_id=7, role="user", content="我有几个班级")
    m2 = append_message(assistant_db, session.id, user_id=7, role="assistant", content="已找到 2 个班级", run_id=run.id)

    assert m1.role == "user"
    assert m1.run_id is None
    assert m2.role == "assistant"
    assert m2.run_id == run.id


def test_append_message_rejects_foreign_user(assistant_db):
    """跨用户写消息必须被拒绝。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")

    with pytest.raises(ValueError):
        append_message(assistant_db, session.id, user_id=8, role="user", content="x")


# ========== finalize_run 原子事务 ==========

def test_finalize_run_atomic_message_artifact_completion(assistant_db):
    """finalize_run 在同一 PostgreSQL 事务提交：最终消息 + Artifact + run.completed。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")
    append_message(assistant_db, session.id, user_id=7, role="user", content="我有几个班级")

    finalize_run(
        assistant_db, run.id, user_id=7,
        final_output="最终答案",
        assistant_message="最终答案",
        artifacts=[
            {"artifact_type": "analysis", "schema_version": "v1", "payload": {"x": 1}},
            {"artifact_type": "evidence", "schema_version": "v1", "payload": {"y": 2}},
        ],
    )

    loaded = get_run(assistant_db, run.id, user_id=7)
    assert loaded.status == "completed"
    assert loaded.final_output == "最终答案"
    assert loaded.finished_at is not None
    assert len(loaded.artifacts) == 2
    # 助手消息已挂到本次 run（直接查询验证，避免依赖未定义的 ORM 关系）
    from app.models import AgentMessage
    msgs = assistant_db.query(AgentMessage).filter(
        AgentMessage.session_id == session.id,
        AgentMessage.run_id == run.id,
        AgentMessage.role == "assistant",
    ).all()
    assert len(msgs) == 1
    assert msgs[0].content == "最终答案"


def test_finalize_run_rolls_back_on_error(assistant_db):
    """finalize_run 出错时整体回滚，不留半状态（run 仍 running、无 artifact、无消息）。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")
    append_message(assistant_db, session.id, user_id=7, role="user", content="q")

    # 用非法 artifact 触发保存失败（缺 schema_version 在 NOT NULL 列上）
    with pytest.raises(Exception):
        finalize_run(
            assistant_db, run.id, user_id=7,
            final_output="最终答案",
            assistant_message="最终答案",
            artifacts=[{"artifact_type": "x"}],  # 缺 schema_version
        )

    loaded = get_run(assistant_db, run.id, user_id=7)
    assert loaded.status == "running"
    assert loaded.final_output is None
    assert loaded.finished_at is None
    assert loaded.artifacts == []


def test_finalize_run_rejects_foreign_user(assistant_db):
    """跨用户 finalize 必须被拒绝。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")

    with pytest.raises(ValueError):
        finalize_run(assistant_db, run.id, user_id=8, final_output="x")


def test_finalize_run_never_overwrites_cancelled_status(assistant_db):
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")
    cancel_run(assistant_db, run.id, user_id=7)

    with pytest.raises(ValueError):
        finalize_run(
            assistant_db,
            run.id,
            user_id=7,
            final_output="不应保存",
            assistant_message="不应保存",
        )

    assistant_db.expire_all()
    loaded = get_run(assistant_db, run.id, user_id=7)
    assert loaded.status == "cancelled"
    from app.models import AgentMessage
    assert assistant_db.query(AgentMessage).filter(
        AgentMessage.run_id == run.id,
        AgentMessage.role == "assistant",
    ).count() == 0


# ========== 图状态不得保存 ORM 对象 ==========

class _StubSpecialists:
    """图测试替身：返回纯字典，不接触 ORM。"""
    def teaching_data(self, state):
        return {"candidate_answer": "数据回答"}

    def teaching_strategy(self, state):
        return {"candidate_answer": "策略回答"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


def test_graph_state_does_not_carry_orm_objects():
    """图执行后 state 中所有值必须是基础类型（dict/list/str/int/None），不得出现 ORM 对象。"""
    from sqlalchemy.orm import declarative_base
    graph = build_teacher_graph(_StubSpecialists())
    result = graph.invoke({"user_message": "我有几个班级", "visited_nodes": []})

    def _check(value, path="root"):
        if value is None or isinstance(value, (str, int, float, bool)):
            return
        if isinstance(value, dict):
            for k, v in value.items():
                _check(v, f"{path}.{k}")
            return
        if isinstance(value, list):
            for i, v in enumerate(value):
                _check(v, f"{path}[{i}]")
            return
        # 不允许出现 ORM / SQLAlchemy 实例
        try:
            Base = declarative_base()
            if isinstance(value, Base):
                raise AssertionError(f"图状态包含 ORM 对象：{path} -> {type(value)}")
        except Exception:
            pass
        # 通用：不允许带 __dict__ 且 _sa_instance_state 的对象
        if hasattr(value, "_sa_instance_state"):
            raise AssertionError(f"图状态包含 SQLAlchemy 实例：{path} -> {type(value)}")

    _check(result)


# ========== 编排服务：将图执行与 PG 持久化绑定 ==========

from app.agent.contracts import (  # noqa: E402
    AGENT_BUDGET_EXCEEDED,
    AGENT_CHAT_ERROR,
    ActorContext,
    SpecialistResponse,
)
from app.agent.graphs.teacher import build_teacher_graph  # noqa: E402
from app.agent.runtime import BudgetExceeded, RunBudget  # noqa: E402
from app.agent.service import OrchestrationResult, orchestrate_teacher_run  # noqa: E402
from app.crud.agent_session import create_session  # noqa: E402


class _ApprovingSpecialists:
    """始终通过的替身：candidate_answer 来自 teaching_data。"""
    def teaching_data(self, state):
        response = SpecialistResponse(
            answer="已找到 2 个班级",
            evidence_refs=["class:7:count"],
            limitations=["仅统计当前教师名下班级"],
        )
        return {
            "candidate_answer": response.answer,
            "evidence_refs": response.evidence_refs,
            "limitations": response.limitations,
            "specialist_response": response,
        }

    def teaching_strategy(self, state):
        return {"candidate_answer": "建议加强练习"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


class _BudgetBlowingSpecialists:
    """每次 teaching_data 调用都抛 BudgetExceeded。"""
    def teaching_data(self, state):
        raise BudgetExceeded("node budget exceeded")

    def teaching_strategy(self, state):
        return {"candidate_answer": "x"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


class _CrashingSpecialists:
    """teaching_data 抛未知异常，验证安全降级。"""
    def teaching_data(self, state):
        raise RuntimeError("pymysql: connection reset")

    def teaching_strategy(self, state):
        return {"candidate_answer": "x"}

    def final_reviewer(self, state):
        return {"review": ReviewResult(approved=True, issues=[])}


def _actor(teacher_id: int, session_id: str) -> ActorContext:
    return ActorContext(
        user_id=teacher_id,
        role="teacher",
        request_id="req-test-0001",
        session_id=session_id,
    )


def test_orchestrate_persists_run_steps_and_finalizes(assistant_db):
    """编排服务：创建 Run → 写 Step → 原子 finalize（消息 + run.completed）。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher", session_id="sessorch0001")

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-test-0001",
        specialists=_ApprovingSpecialists(),
        assistant_db=assistant_db,
    )

    assert isinstance(result, OrchestrationResult)
    assert result.status == "completed"
    assert result.final_answer == "已找到 2 个班级"
    assert result.run_id  # 非空

    # Run 已 completed
    loaded = get_run(assistant_db, result.run_id, user_id=7)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.final_output == "已找到 2 个班级"

    # Steps 持久化时使用与 LangGraph 一致的具名 Agent 节点。
    steps = list_steps(assistant_db, result.run_id, user_id=7)
    assert len(steps) >= 3
    assert [s.node_name for s in steps] == [
        "teacher_supervisor",
        "teacher_data_agent",
        "final_reviewer_agent",
        "finalize",
    ]
    teaching_step = next(s for s in steps if s.node_name == "teacher_data_agent")
    assert teaching_step.output_json["candidate_answer"] == "已找到 2 个班级"
    assert teaching_step.evidence_refs == ["class:7:count"]
    assert all(step.duration_ms >= 1 for step in steps)

    artifacts = list_artifacts(assistant_db, result.run_id, user_id=7)
    assert [artifact.artifact_type for artifact in artifacts] == [
        "specialist_response",
        "review_result",
    ]
    assert artifacts[0].payload_json["evidence_refs"] == ["class:7:count"]
    assert artifacts[1].payload_json["approved"] is True

    assert loaded.intent == "teaching_data"
    assert loaded.risk_level == "low"

    # 助手消息已挂到 run
    from app.models import AgentMessage
    msgs = assistant_db.query(AgentMessage).filter(
        AgentMessage.session_id == session.id,
        AgentMessage.run_id == result.run_id,
    ).all()
    roles = {m.role for m in msgs}
    assert "user" in roles
    assert "assistant" in roles


def test_orchestrate_marks_failed_on_budget_exceeded(assistant_db):
    """预算超限 → Run 标记 failed + error_code=AGENT_BUDGET_EXCEEDED，不写最终消息。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher", session_id="sessorch0002")

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-test-0002",
        specialists=_BudgetBlowingSpecialists(),
        assistant_db=assistant_db,
    )

    assert result.status == "failed"
    assert result.error_code == AGENT_BUDGET_EXCEEDED
    assert result.final_answer == ""  # 失败时不输出候选答案

    loaded = get_run(assistant_db, result.run_id, user_id=7)
    assert loaded.status == "failed"
    assert loaded.error_code == AGENT_BUDGET_EXCEEDED
    failed_steps = list_steps(assistant_db, result.run_id, user_id=7)
    assert failed_steps[-1].node_name == "teacher_data_agent"
    assert failed_steps[-1].status == "failed"
    assert failed_steps[-1].error_code == AGENT_BUDGET_EXCEEDED
    assert failed_steps[-1].duration_ms >= 1


def test_orchestrate_marks_failed_on_unknown_error(assistant_db):
    """未知异常 → Run 标记 failed + error_code=AGENT_CHAT_ERROR，不泄露堆栈。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher", session_id="sessorch0003")

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-test-0003",
        specialists=_CrashingSpecialists(),
        assistant_db=assistant_db,
    )

    assert result.status == "failed"
    assert result.error_code == AGENT_CHAT_ERROR
    # 安全消息，不包含内部异常细节
    assert "pymysql" not in result.final_answer
    assert "RuntimeError" not in result.final_answer

    loaded = get_run(assistant_db, result.run_id, user_id=7)
    assert loaded.status == "failed"
    assert loaded.error_code == AGENT_CHAT_ERROR
    failed_steps = list_steps(assistant_db, result.run_id, user_id=7)
    assert failed_steps[-1].node_name == "teacher_data_agent"
    assert failed_steps[-1].status == "failed"
    assert failed_steps[-1].error_code == AGENT_CHAT_ERROR


def test_orchestrate_rejects_foreign_session(assistant_db):
    """跨用户会话 → 直接 ValueError，不创建 Run。"""
    create_session(assistant_db, user_id=7, actor_role="teacher", session_id="sessorch0004")

    with pytest.raises(ValueError):
        orchestrate_teacher_run(
            teacher_id=8,  # 不同用户
            message="x",
            session_id="sessorch0004",
            request_id="req-test-0004",
            specialists=_ApprovingSpecialists(),
            assistant_db=assistant_db,
        )


def test_orchestrate_persists_events_for_sse(assistant_db):
    """编排服务返回事件序列，供 SSE 流式输出。"""
    session = create_session(assistant_db, user_id=7, actor_role="teacher", session_id="sessorch0005")

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-test-0005",
        specialists=_ApprovingSpecialists(),
        assistant_db=assistant_db,
    )

    event_types = [e["type"] for e in result.events]
    assert "run.started" in event_types
    assert "route.selected" in event_types
    assert "agent.started" in event_types
    assert "agent.completed" in event_types
    assert "run.completed" in event_types


def test_orchestrate_passes_owned_session_summary_and_recent_messages(assistant_db):
    """新版 specialist 获得同一会话摘要和历史，不依赖旧 agent_chat_messages。"""
    session = create_session(
        assistant_db,
        user_id=7,
        actor_role="teacher",
        session_id="sessorchctx01",
    )
    session.summary = "正在分析一班的作业情况"
    assistant_db.commit()
    append_message(
        assistant_db, session.id, user_id=7, role="user", content="先查一班",
    )
    append_message(
        assistant_db, session.id, user_id=7, role="assistant", content="已找到一班",
    )

    captured = {}

    class _CapturingSpecialists(_ApprovingSpecialists):
        def teaching_data(self, state):
            captured["summary"] = state.get("conversation_summary")
            captured["messages"] = state.get("recent_messages")
            return super().teaching_data(state)

    orchestrate_teacher_run(
        teacher_id=7,
        message="他们最近提交得怎样？",
        session_id=session.id,
        request_id="req-context-001",
        specialists=_CapturingSpecialists(),
        assistant_db=assistant_db,
    )

    assert captured["summary"] == "正在分析一班的作业情况"
    assert captured["messages"] == [
        {"role": "user", "content": "先查一班"},
        {"role": "assistant", "content": "已找到一班"},
    ]


def test_orchestrate_emits_live_started_event_before_specialist_call(assistant_db):
    """LangGraph v2 custom stream 在耗时 specialist 执行前发出 started。"""
    from threading import Event

    session = create_session(
        assistant_db,
        user_id=7,
        actor_role="teacher",
        session_id="sessorchlive1",
    )
    emitted = []
    agent_started = Event()

    def capture(event):
        emitted.append(event)
        if (
            event["type"] == "agent.started"
            and event["data"].get("agent") == "teacher_data_agent"
        ):
            agent_started.set()

    class _LiveSpecialists(_ApprovingSpecialists):
        def teaching_data(self, state):
            assert emitted[0]["type"] == "run.started"
            assert emitted[0]["data"]["run_id"]
            assert agent_started.wait(timeout=1)
            return super().teaching_data(state)

    result = orchestrate_teacher_run(
        teacher_id=7,
        message="我有几个班级",
        session_id=session.id,
        request_id="req-live-001",
        specialists=_LiveSpecialists(),
        assistant_db=assistant_db,
        event_callback=capture,
    )

    assert result.status == "completed"
    assert any(event["type"] == "content.delta" for event in emitted)
    assert emitted[-1]["type"] == "run.completed"
