from pathlib import Path


def test_validation_agent_uses_shared_database_config() -> None:
    text = Path("scripts/run_employer_origin_connector_validation_agent.py").read_text(encoding="utf-8")

    assert "from src.config import get_database_config" in text
    assert "psycopg.connect(**get_database_config())" in text
    assert "DatabaseConfig.from_environment()" not in text
    assert "os.environ[" not in text
