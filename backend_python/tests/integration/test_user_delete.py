"""删除用户的跨库清理测试：删用户时 PG 会话库的 AgentChatMessage 应被清理，且不触发跨库异常。"""
from app.crud import agent_chat as chat_crud
from app.crud import user as user_crud
from app.models import AgentChatMessage, User


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
