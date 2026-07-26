"""删除用户的跨库清理测试：删用户时 PG 会话库的 AgentChatMessage/Agent 多智能体表
应被清理，MySQL 侧审批账本同步清理，且不触发跨库异常。"""
from datetime import datetime, timedelta

from app.crud import agent_chat as chat_crud
from app.crud import user as user_crud
from app.models import (
    AgentActionExecution,
    AgentApproval,
    AgentArtifact,
    AgentChatMessage,
    AgentMessage,
    AgentRun,
    AgentSession,
    AgentStep,
    User,
)


def _seed_agent_data(db, assistant_db, user, tag: str) -> str:
    """为用户构造一整套多智能体数据，返回审批幂等键。"""
    session = AgentSession(
        id=f"sess-{tag}-0001",
        user_id=user.id,
        actor_role=user.role,
        title="测试会话",
    )
    assistant_db.add(session)
    run = AgentRun(
        id=f"{tag[:1] * 32}",
        session_id=session.id,
        user_id=user.id,
        intent="teacher_query",
        status="completed",
        started_at=datetime.now(),
    )
    assistant_db.add(run)
    assistant_db.flush()
    assistant_db.add(AgentStep(
        run_id=run.id, sequence=1, node_name="supervisor", status="completed",
    ))
    assistant_db.add(AgentArtifact(
        run_id=run.id, artifact_type="answer", schema_version="v1", payload_json={},
    ))
    assistant_db.add(AgentMessage(
        session_id=session.id, run_id=run.id, role="user", content="你好",
    ))
    idem_key = f"idem-{tag}-key"
    assistant_db.add(AgentApproval(
        id=f"approval-{tag}-0001",
        requester_user_id=user.id,
        requester_role=user.role,
        action_type="create_ai_rule",
        target_type="ai_rule",
        payload_json={},
        payload_hash="h" * 64,
        idempotency_key=idem_key,
        summary="测试审批",
        risk_level="medium",
        status="pending",
        expires_at=datetime.now() + timedelta(minutes=10),
    ))
    assistant_db.commit()
    db.add(AgentActionExecution(
        idempotency_key=idem_key, action_type="create_ai_rule", status="completed",
    ))
    db.commit()
    return idem_key


def test_delete_user_cleans_pg_chat_history(db, assistant_db, user_factory):
    teacher = user_factory("t_del", "teacher")
    chat_crud.save_exchange(assistant_db, teacher.id, "s1", "问题", "回答")
    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=teacher.id).count() == 2

    user_crud.delete_user(db, teacher.id)  # 修复前：OperationalError；修复后：正常

    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=teacher.id).count() == 0
    assert db.query(User).filter_by(id=teacher.id).count() == 0


def test_delete_users_batch_cleans_pg_chat_history(db, assistant_db, user_factory):
    teacher = user_factory("t_batch", "teacher")
    chat_crud.save_exchange(assistant_db, teacher.id, "s1", "q", "a")
    result = user_crud.delete_users_batch(db, [str(teacher.id)])
    assert result["successCount"] == 1
    assert result["failureCount"] == 0
    assert assistant_db.query(AgentChatMessage).filter_by(teacher_id=teacher.id).count() == 0


def test_delete_user_cleans_agent_runtime_tables(db, assistant_db, user_factory):
    """删用户须清理新多智能体表（会话/运行/步骤/产物/消息/审批）及 MySQL 审批账本。"""
    teacher = user_factory("t_agent_del", "teacher")
    idem_key = _seed_agent_data(db, assistant_db, teacher, "a")

    user_crud.delete_user(db, teacher.id)

    assistant_db.expire_all()
    db.expire_all()
    assert assistant_db.query(AgentSession).filter_by(user_id=teacher.id).count() == 0
    assert assistant_db.query(AgentRun).filter_by(user_id=teacher.id).count() == 0
    assert assistant_db.query(AgentStep).count() == 0
    assert assistant_db.query(AgentArtifact).count() == 0
    assert assistant_db.query(AgentMessage).count() == 0
    assert assistant_db.query(AgentApproval).filter_by(requester_user_id=teacher.id).count() == 0
    assert db.query(AgentActionExecution).filter_by(idempotency_key=idem_key).count() == 0
    assert db.query(User).filter_by(id=teacher.id).count() == 0


def test_delete_user_keeps_other_users_agent_data(db, assistant_db, user_factory):
    """删除一个用户不得误删其他用户的多智能体数据。"""
    victim = user_factory("t_victim", "teacher")
    survivor = user_factory("t_survivor", "teacher")
    _seed_agent_data(db, assistant_db, victim, "b")
    survivor_key = _seed_agent_data(db, assistant_db, survivor, "c")

    user_crud.delete_user(db, victim.id)

    assistant_db.expire_all()
    db.expire_all()
    assert assistant_db.query(AgentSession).filter_by(user_id=survivor.id).count() == 1
    assert assistant_db.query(AgentRun).filter_by(user_id=survivor.id).count() == 1
    assert assistant_db.query(AgentStep).count() == 1
    assert assistant_db.query(AgentArtifact).count() == 1
    assert assistant_db.query(AgentMessage).count() == 1
    assert assistant_db.query(AgentApproval).filter_by(requester_user_id=survivor.id).count() == 1
    assert db.query(AgentActionExecution).filter_by(idempotency_key=survivor_key).count() == 1
