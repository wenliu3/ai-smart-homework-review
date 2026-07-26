"""LangGraph PostgreSQL 持久化检查点工厂。"""
from __future__ import annotations

import threading
import atexit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from ..config import settings

_lock = threading.Lock()
_pool: ConnectionPool | None = None
_saver: PostgresSaver | None = None


def get_graph_checkpointer():
    """延迟创建进程级 PostgreSQL saver；测试 SQLite 环境不启用。"""
    global _pool, _saver
    database_url = settings.ASSISTANT_DATABASE_URL
    if not database_url.startswith(("postgresql://", "postgres://")):
        return None
    if _saver is not None:
        return _saver
    with _lock:
        if _saver is not None:
            return _saver
        pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=5,
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        pool.open(wait=True, timeout=10)
        saver = PostgresSaver(pool)
        saver.setup()
        _pool = pool
        _saver = saver
        return saver


def close_graph_checkpointer() -> None:
    """关闭进程级连接池，供应用生命周期结束时调用。"""
    global _pool, _saver
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _saver = None


atexit.register(close_graph_checkpointer)


__all__ = ["close_graph_checkpointer", "get_graph_checkpointer"]
