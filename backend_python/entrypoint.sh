#!/bin/bash
set -e

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlsplit

dependencies = (
    ("MySQL", "DATABASE_URL", 3306),
    ("PostgreSQL", "ASSISTANT_DATABASE_URL", 5432),
    ("Redis", "REDIS_URL", 6379),
)

for name, variable, default_port in dependencies:
    parsed = urlsplit(os.environ[variable])
    host = parsed.hostname
    port = parsed.port or default_port
    for attempt in range(1, 31):
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{name} is ready")
                break
        except OSError:
            print(f"Waiting for {name} ({attempt}/30)")
            time.sleep(2)
    else:
        raise SystemExit(f"{name} connection timed out")
PY

# 既有部署检测：旧版 entrypoint 只跑 seed.py（create_all 建表），库里已有全部业务表
# 但没有 alembic_version 表。此时直接 upgrade head 会重复 create_table 而崩溃，
# 需要先 stamp 基线版本再 upgrade。
# 判定规则：alembic_version 不存在 且 标志表存在（MySQL 查 users，PG 查 agent_chat_messages）
# 时输出 stamp，否则输出 none。探测失败输出为空，走 none 分支，由后续 upgrade 报错。
detect_stamp_action() {
    ALEMBIC_PROBE_URL="$1" ALEMBIC_PROBE_MARKER_TABLE="$2" python - <<'PY'
import os

from sqlalchemy import create_engine, inspect

engine = create_engine(os.environ["ALEMBIC_PROBE_URL"], pool_pre_ping=True)
try:
    inspector = inspect(engine)
    has_version = inspector.has_table("alembic_version")
    has_marker = inspector.has_table(os.environ["ALEMBIC_PROBE_MARKER_TABLE"])
finally:
    engine.dispose()

print("stamp" if (has_marker and not has_version) else "none")
PY
}

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    if [ "$(detect_stamp_action "${ALEMBIC_DATABASE_URL:-${DATABASE_URL}}" "users")" = "stamp" ]; then
        echo "Existing MySQL schema without alembic_version detected, stamping baseline"
        alembic stamp 9e5b9284446d
    fi
    alembic upgrade head

    if [ "$(detect_stamp_action "${ALEMBIC_ASSISTANT_DATABASE_URL:-${ASSISTANT_DATABASE_URL}}" "agent_chat_messages")" = "stamp" ]; then
        echo "Existing PostgreSQL schema without alembic_version detected, stamping baseline"
        alembic -c alembic_assistant.ini stamp 20260724_00
    fi
    alembic -c alembic_assistant.ini upgrade head

    python seed.py
fi

exec "$@"
