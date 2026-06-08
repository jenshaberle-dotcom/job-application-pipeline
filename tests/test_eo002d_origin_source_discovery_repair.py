from __future__ import annotations

from pathlib import Path

from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryProbeResult,
    discover_origin_source,
    generate_company_url_candidates,
)


def accepted_probe(url: str) -> OriginDiscoveryProbeResult:
    return OriginDiscoveryProbeResult(
        url=url,
        final_url=url,
        status_code=200,
        reachable=True,
        career_like=True,
        response_bytes=2048,
        title="Accepted career page",
        reason="fake accepted career page",
    )


def test_hannover_re_alias_domains_are_in_default_budget() -> None:
    urls = [item.url for item in generate_company_url_candidates(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        max_candidates=30,
    )]

    assert "https://jobs.hannover-re.com/" in urls
    assert any(url.startswith("https://www.hannover-re.com/de/karriere") for url in urls)
    assert all("jobs.hannover.de" not in url for url in urls)


def test_hannover_re_alias_domains_can_be_selected_without_external_search() -> None:
    result = discover_origin_source(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        source_family_candidate="hannover_ruck",
        probe=accepted_probe,
        max_generated_candidates=30,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_url is not None
    assert "hannover-re.com" in result.selected_url


def test_eon_parent_career_domains_are_in_default_budget() -> None:
    urls = [item.url for item in generate_company_url_candidates(
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        source_family_candidate="e_on_grid_solutions",
        max_candidates=30,
    )]

    assert "https://careers.eon.com/" in urls
    assert any(url.startswith("https://www.eon.com/de/karriere") for url in urls)
    assert all("jobs.grid.de" not in url for url in urls)


def test_eon_parent_career_domains_can_be_selected_without_external_search() -> None:
    result = discover_origin_source(
        company_key="e_on_grid_solutions",
        company_name="E.ON Grid Solutions GmbH",
        source_family_candidate="e_on_grid_solutions",
        probe=accepted_probe,
        max_generated_candidates=30,
    )

    assert result.decision == "origin_url_candidate_selected"
    assert result.selected_url is not None
    assert "eon.com" in result.selected_url


def test_eo002d_docs_record_boundaries_and_next_decision() -> None:
    doc = Path("docs/archive/planning/eo002d_origin_source_discovery_url_finder_repair.md").read_text(encoding="utf-8")
    roadmap = Path("docs/planning/active/roadmap.md").read_text(encoding="utf-8")
    current_state = Path("docs/reference/search-intelligence/current_state.md").read_text(encoding="utf-8")

    assert "EO-002D Origin Source Discovery / URL Finder Repair" in doc
    assert "no scheduler change" in doc
    assert "no candidate URL write" in current_state
    assert "EO-002D-ROADMAP" in roadmap
    assert "Hannover Rück" in doc
    assert "E.ON Grid Solutions" in doc
