import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend_python"


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _baseline_revision(relative_path: str) -> str:
    match = re.search(
        r"^revision(?::\s*str)?\s*=\s*['\"]([^'\"]+)['\"]",
        _read(relative_path),
        flags=re.MULTILINE,
    )
    assert match is not None, f"no revision id found in {relative_path}"
    return match.group(1)


def test_backend_image_uses_python_312() -> None:
    dockerfile = _read("backend_python/Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "FROM python:3.11" not in dockerfile


def test_backend_image_retries_transient_apt_download_failures() -> None:
    dockerfile = _read("backend_python/Dockerfile")

    assert dockerfile.count("Acquire::Retries=5") == 2


def test_backend_dockerignore_excludes_pytest_runtime_directories() -> None:
    dockerignore = _read("backend_python/.dockerignore")

    assert ".pytest_cache/" in dockerignore
    assert ".pytest-review-*/" in dockerignore


def test_entrypoint_waits_for_all_runtime_dependencies() -> None:
    entrypoint = _read("backend_python/entrypoint.sh")

    assert "DATABASE_URL" in entrypoint
    assert "ASSISTANT_DATABASE_URL" in entrypoint
    assert "REDIS_URL" in entrypoint
    assert "socket.create_connection" in entrypoint


def test_entrypoint_runs_both_migration_sets_before_forwarding_command() -> None:
    entrypoint = _read("backend_python/entrypoint.sh")

    mysql_migration = "alembic upgrade head"
    assistant_migration = "alembic -c alembic_assistant.ini upgrade head"
    command_forwarding = 'exec "$@"'

    assert mysql_migration in entrypoint
    assert assistant_migration in entrypoint
    assert command_forwarding in entrypoint
    assert entrypoint.index(mysql_migration) < entrypoint.index(assistant_migration)
    assert entrypoint.index(assistant_migration) < entrypoint.index(command_forwarding)
    assert "uvicorn app.main:app" not in entrypoint


def test_entrypoint_stamps_baselines_for_preexisting_schemas() -> None:
    """既有部署（旧版 create_all 建表、无 alembic_version）升级时须先 stamp 基线再 upgrade。"""
    entrypoint = _read("backend_python/entrypoint.sh")
    mysql_baseline = _baseline_revision(
        "backend_python/alembic/versions/9e5b9284446d_baseline.py",
    )
    assistant_baseline = _baseline_revision(
        "backend_python/alembic_assistant/versions/20260724_00_baseline.py",
    )

    mysql_stamp = f"alembic stamp {mysql_baseline}"
    assistant_stamp = f"alembic -c alembic_assistant.ini stamp {assistant_baseline}"

    # stamp 命令使用的基线版本号必须与迁移文件中的 revision id 一致
    assert mysql_stamp in entrypoint
    assert assistant_stamp in entrypoint

    # 探测要素：检查 alembic_version 缺失 + 标志表存在（MySQL 查 users，PG 查 agent_chat_messages）
    assert "alembic_version" in entrypoint
    assert '"users"' in entrypoint
    assert '"agent_chat_messages"' in entrypoint
    assert "has_marker and not has_version" in entrypoint

    # stamp 是条件分支（既有库才 stamp），不能无条件执行
    assert '= "stamp" ]' in entrypoint

    # stamp 必须发生在对应的 upgrade head 之前
    assert entrypoint.index(mysql_stamp) < entrypoint.index("alembic upgrade head")
    assert entrypoint.index(assistant_stamp) < entrypoint.index(
        "alembic -c alembic_assistant.ini upgrade head",
    )

    # 两侧探测分别使用各自数据库的连接串（含 alembic 环境变量覆盖优先）
    assert '"${ALEMBIC_DATABASE_URL:-${DATABASE_URL}}"' in entrypoint
    assert '"${ALEMBIC_ASSISTANT_DATABASE_URL:-${ASSISTANT_DATABASE_URL}}"' in entrypoint


def test_only_backend_runs_migrations_to_avoid_startup_races() -> None:
    entrypoint = _read("backend_python/entrypoint.sh")
    compose = yaml.safe_load(_read("docker-compose.yml"))

    assert 'if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then' in entrypoint
    assert compose["services"]["backend"]["environment"]["RUN_MIGRATIONS"] == 1
    assert compose["services"]["worker"]["environment"]["RUN_MIGRATIONS"] == 0
    assert "python seed.py" in entrypoint
    assert entrypoint.index(
        "alembic -c alembic_assistant.ini upgrade head",
    ) < entrypoint.index("python seed.py")


def test_compose_defines_commands_for_backend_and_worker() -> None:
    compose = yaml.safe_load(_read("docker-compose.yml"))
    services = compose["services"]

    assert "uvicorn app.main:app" in services["backend"]["command"]
    assert "celery" in services["worker"]["command"]


def test_compose_requires_secrets_without_containing_their_values() -> None:
    compose_text = _read("docker-compose.yml")

    for variable in ("MYSQL_ROOT_PASSWORD", "POSTGRES_PASSWORD", "JWT_SECRET"):
        assert f"${{{variable}:?" in compose_text

    # .env.docker 是本地私密文件（gitignored）：CI 全新检出没有它，
    # 只在本机存在时校验「真实密钥值不泄漏进 compose 文本」
    if not (REPO_ROOT / ".env.docker").exists():
        pytest.skip(".env.docker 不存在（CI 环境），跳过密钥泄漏比对")

    env_values = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in _read(".env.docker").splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    for variable in ("MYSQL_ROOT_PASSWORD", "POSTGRES_PASSWORD", "JWT_SECRET"):
        assert env_values[variable]
        assert env_values[variable] not in compose_text


def test_compose_exposes_mysql_for_navicat_and_keeps_internal_backend_address() -> None:
    compose_text = _read("docker-compose.yml")
    compose = yaml.safe_load(compose_text)

    assert "docker compose --env-file .env.docker up -d" in compose_text
    assert compose["services"]["mysql"]["ports"] == ["127.0.0.1:3307:3306"]
    for service in ("postgres", "redis"):
        assert all(
            str(port).startswith("127.0.0.1:")
            for port in compose["services"][service]["ports"]
        )
    assert "@mysql:3306/ai_smart_review" in compose["services"]["backend"]["environment"]["DATABASE_URL"]


def test_frontend_nginx_resolves_service_names_only_with_docker_dns() -> None:
    nginx_config = _read("frontend/nginx.conf")

    assert "resolver 127.0.0.11 valid=30s ipv6=off;" in nginx_config
    assert "8.8.8.8" not in nginx_config


def test_frontend_nginx_allows_backend_upload_limit_with_multipart_overhead() -> None:
    nginx_config = _read("frontend/nginx.conf")

    # 业务层按单文件 20 MiB 校验；Nginx 只拦截异常大的请求，避免抢先返回 413。
    assert "client_max_body_size 100m;" in nginx_config
