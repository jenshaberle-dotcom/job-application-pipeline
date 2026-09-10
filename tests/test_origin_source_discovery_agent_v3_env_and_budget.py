from pathlib import Path

SCRIPT = Path("scripts/run_origin_source_discovery_agent.py").read_text(encoding="utf-8")


def test_agent_loads_local_env_without_dotenv_dependency() -> None:
    assert "def load_local_env_file(" in SCRIPT
    assert "os.environ[key] = value" in SCRIPT
    assert "load_local_env_file()" in SCRIPT


def test_agent_labels_f1_v4_and_keeps_bounded_search_http_budget() -> None:
    assert "Origin Source Discovery Agent v4 / F1 jobspace expansion" in SCRIPT
    assert 'parser.add_argument("--http-request-cap", type=int, default=48)' in SCRIPT
    assert "HttpDiscoveryClient" in SCRIPT


def test_f1_official_domain_and_surface_layers_remain_optional_and_read_only() -> None:
    assert 'choices=("none", "wikidata")' in SCRIPT
    assert "--official-domain-url" in SCRIPT
    assert "--no-surface-expansion" in SCRIPT
    assert "official-domain evidence never bypasses company identity or proof" in SCRIPT
    assert "discover_official_origin_jobspace" in SCRIPT
