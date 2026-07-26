"""一次性迁移：MySQL agent_chat_messages → PostgreSQL 会话库（幂等，可重复执行）。

用法（backend_python 目录）：
    python -m scripts.migrate_agent_chat_to_pg

模型已迁移到 AssistantBase，MySQL 旧表通过 Core 反射读取，不依赖 ORM。
判重键：(teacher_id, session_id, role, content, created_at)。
"""
from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.exc import NoSuchTableError

from app.assistant_database import AssistantBase, AssistantSessionLocal, assistant_engine
from app.config import settings
from app.models import AgentChatMessage


def main() -> None:
    src = create_engine(settings.DATABASE_URL)
    meta = MetaData()
    try:
        legacy = Table("agent_chat_messages", meta, autoload_with=src)
    except NoSuchTableError:
        print("MySQL 中不存在 agent_chat_messages 表，无需迁移")
        return

    AssistantBase.metadata.create_all(bind=assistant_engine)
    with src.connect() as sconn, AssistantSessionLocal() as tconn:
        rows = sconn.execute(select(legacy)).mappings().all()
        if not rows:
            print("MySQL agent_chat_messages 无数据，无需迁移")
            return
        existing = {
            (m.teacher_id, m.session_id, m.role, m.content, m.created_at)
            for m in tconn.query(AgentChatMessage).all()
        }
        inserted = 0
        for r in rows:
            key = (r["teacher_id"], r["session_id"], r["role"], r["content"], r["created_at"])
            if key in existing:
                continue
            tconn.add(AgentChatMessage(
                teacher_id=r["teacher_id"], session_id=r["session_id"],
                role=r["role"], content=r["content"],
                created_at=r.get("created_at"), updated_at=r.get("updated_at"),
            ))
            inserted += 1
            existing.add(key)
        tconn.commit()
        print(f"迁移完成：MySQL 共 {len(rows)} 条，新增 {inserted} 条，跳过 {len(rows) - inserted} 条")


if __name__ == "__main__":
    main()
