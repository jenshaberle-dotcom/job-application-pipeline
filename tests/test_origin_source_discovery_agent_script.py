from pathlib import Path

SCRIPT = Path("scripts/run_origin_source_discovery_agent.py").read_text(encoding="utf-8")


def test_origin_source_discovery_agent_is_read_only() -> None:
    assert "no candidate_url write" in SCRIPT
    assert "UPDATE employer_origin_source_candidates" not in SCRIPT
    assert "INSERT INTO" not in SCRIPT
    assert "--apply" not in SCRIPT


def test_origin_source_discovery_agent_supports_bounded_probe_controls() -> None:
    assert "--timeout-seconds" in SCRIPT
    assert "--max-candidates" in SCRIPT
    assert "--no-probe" in SCRIPT


def test_origin_source_discovery_agent_supports_tavily_search_provider() -> None:
    assert "--search-provider" in SCRIPT
    assert 'choices=("none", "tavily")' in SCRIPT
    assert "--search-results-json" in SCRIPT
    assert "TAVILY_API_KEY" in SCRIPT


def test_origin_source_discovery_agent_prints_search_results_for_review() -> None:
    assert 'payload["search_results"]' in SCRIPT
    assert 'print("search_results:")' in SCRIPT
