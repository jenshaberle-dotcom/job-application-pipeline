from __future__ import annotations

from src.search_intelligence.adaptive_origin_search import (
    SearchProgressLedger,
    brand_surface_variants,
    deterministic_brand_url_hypotheses,
    domain_followup_queries,
    initial_adaptive_queries,
    validate_search_hypotheses,
)


def test_symbol_numeric_brand_keeps_domain_identity() -> None:
    variants = brand_surface_variants(
        company_name="1&1",
        company_key="1_1",
    )

    assert variants[0] == "1&1"
    assert "1and1" in variants
    assert "1-and-1" in variants


def test_symbol_brand_career_org_host_is_inside_first_budget() -> None:
    urls = deterministic_brand_url_hypotheses(
        company_name="1&1",
        company_key="1_1",
        maximum=6,
    )

    assert urls[0] == "https://career.1and1.org/"
    assert "https://careers.1and1.org/" in urls
    assert "https://jobs.1and1.org/" in urls


def test_global_human_search_precedes_location_filtering() -> None:
    queries = initial_adaptive_queries(
        company_name="1&1",
        company_key="1_1",
        target_location="Hannover",
        maximum=6,
    )

    assert queries[:3] == (
        '"1&1" Karriere',
        '"1&1" careers',
        '"1&1" offizielle Karriereseite',
    )
    assert '"1and1" Karriere' in queries
    assert queries[-1] == '"1&1" Jobs Hannover'


def test_domain_followup_is_bounded_and_skips_aggregators() -> None:
    queries = domain_followup_queries(
        ["www.1and1.org", "stepstone.de", "career.1and1.org"],
        maximum=3,
    )

    assert queries == (
        "site:1and1.org career",
        "site:1and1.org jobs",
        "site:career.1and1.org career",
    )
    assert all("stepstone" not in query for query in queries)


def test_ledger_refuses_identical_queries_and_urls() -> None:
    ledger = SearchProgressLedger()

    assert ledger.novel_queries(["  1and1   careers  "]) == ("1and1   careers",)
    assert ledger.novel_queries(["1AND1 careers"]) == ()
    assert ledger.novel_urls(["https://career.1and1.org/?page=1"]) == (
        "https://career.1and1.org/",
    )
    assert ledger.novel_urls(["https://career.1and1.org/"]) == ()


def test_llm_hypotheses_are_filtered_to_novel_non_aggregator_inputs() -> None:
    ledger = SearchProgressLedger()
    ledger.novel_queries(["1and1 careers"])
    ledger.novel_urls(["https://career.1and1.org/"])

    hypotheses = validate_search_hypotheses(
        {
            "queries": [
                "1and1 careers",
                "site:1and1.org jobs",
                "1&1 official career",
            ],
            "urls": [
                "https://career.1and1.org/",
                "https://jobs.1and1.org/",
                "https://www.stepstone.de/1and1",
            ],
            "rationale": "Try a compact brand and official-domain site search.",
        },
        ledger=ledger,
    )

    assert hypotheses.queries == (
        "site:1and1.org jobs",
        "1&1 official career",
    )
    assert hypotheses.urls == ("https://jobs.1and1.org/",)


def test_repeated_discovery_state_is_visible_and_cannot_be_mistaken_for_progress() -> None:
    ledger = SearchProgressLedger()
    payload = {
        "decision": "not_found",
        "confidence_score": 0.65,
        "search_results": [{"url": "https://example.org/career"}],
    }

    first_fingerprint, first_progress = ledger.record_state(payload)
    second_fingerprint, second_progress = ledger.record_state(dict(payload))

    assert first_fingerprint == second_fingerprint
    assert first_progress is True
    assert second_progress is False
    assert ledger.to_json()["repeated_state_detected"] is True
