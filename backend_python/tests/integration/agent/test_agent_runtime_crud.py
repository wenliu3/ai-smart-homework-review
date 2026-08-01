"""PostgreSQL Agent 会话与运行生命周期测试。"""
from app.crud.agent_run import (
    append_step,
    complete_run,
    create_run,
    create_session,
    get_run,
)


def test_run_lifecycle_is_owned_by_actor(assistant_db):
    session = create_session(assistant_db, user_id=7, actor_role="teacher")
    run = create_run(assistant_db, session.id, user_id=7, intent="teaching_data")
    append_step(assistant_db, run.id, "teaching_data", "completed", {"count": 2})
    complete_run(assistant_db, run.id, "已找到两个班级")

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
