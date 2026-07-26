"""基线迁移测试：upgrade head 建出全部既有表；downgrade base 全部删除。

使用程序化 Alembic API + 独立 SQLite 临时库，不触达开发 MySQL。
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "users", "refresh_tokens", "classes", "class_students",
    "assignments", "submissions", "ai_models", "ai_rules",
    "menus", "roles", "operation_logs",
}


def _make_config(db_path: Path) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def _table_names(db_path: Path) -> set:
    insp = inspect(create_engine(f"sqlite:///{db_path.as_posix()}"))
    return set(insp.get_table_names())


def test_upgrade_head_creates_all_existing_tables(tmp_path):
    db_path = tmp_path / "upgrade.db"
    command.upgrade(_make_config(db_path), "head")
    assert EXPECTED_TABLES <= _table_names(db_path)


def test_upgrade_head_adds_assignment_soft_delete_column(tmp_path):
    """开发态走 create_all，只有这里能发现迁移漏加列。"""
    db_path = tmp_path / "softdelete.db"
    command.upgrade(_make_config(db_path), "head")

    insp = inspect(create_engine(f"sqlite:///{db_path.as_posix()}"))
    columns = {col["name"] for col in insp.get_columns("assignments")}
    assert "deleted_at" in columns


def test_downgrade_base_drops_all_tables(tmp_path):
    db_path = tmp_path / "downgrade.db"
    cfg = _make_config(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    assert EXPECTED_TABLES.isdisjoint(_table_names(db_path))
