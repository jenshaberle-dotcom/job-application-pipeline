from pathlib import Path

SCRIPT = Path("scripts/run_origin_source_discovery_agent.py").read_text(encoding="utf-8")


def test_agent_loads_local_env_without_dotenv_dependency() -> None:
    assert "def load_local_env_file(" in SCRIPT
    assert "os.environ[key] = value" in SCRIPT
    assert "load_local_env_file()" in SCRIPT


def test_agent_labels_v3_and_shows_search_budget() -> None:
    assert "Origin Source Discovery Agent v3" in SCRIPT
