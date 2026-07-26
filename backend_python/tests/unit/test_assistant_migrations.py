"""PostgreSQL Agent 状态库的部署与迁移边界测试。"""
from pathlib import Path

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def _compose_config() -> dict:
    return yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_declares_postgres_and_backend_dependency():
    config = _compose_config()
    postgres = config["services"]["postgres"]

    assert postgres["healthcheck"]
    assert config["services"]["backend"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert "ASSISTANT_DATABASE_URL" in config["services"]["backend"]["environment"]
    assert "postgres_data" in config["volumes"]


def test_docker_environment_declares_postgres_password():
    content = (PROJECT_ROOT / ".env.docker").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=" in content


def test_assistant_alembic_has_baseline_revision():
    assert (BACKEND_ROOT / "alembic_assistant.ini").is_file()
    assert (BACKEND_ROOT / "alembic_assistant" / "env.py").is_file()
    versions = list((BACKEND_ROOT / "alembic_assistant" / "versions").glob("*.py"))
    assert any("baseline" in path.name for path in versions)


def test_app_startup_does_not_create_assistant_tables():
    source = (BACKEND_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "AssistantBase.metadata.create_all" not in source
