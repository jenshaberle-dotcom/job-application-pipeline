from argparse import Namespace

import pytest

from scripts.run_job_first_employer_discovery_census_comparison import (
    _incremental_metrics,
    _run_external_index_sources,
)
from src.search_intelligence.census_flight_authority import (
    resolve_census_flight_authority,
)


def test_none_is_default_zero_request_authority():
    authority = resolve_census_flight_authority(provider="none")
    assert authority.status == "plan_only"
    assert authority.external_requests_authorized is False
    assert authority.paid_external_tool is False


def test_tavily_requires_explicit_paid_provider_opt_in():
    denied = resolve_census_flight_authority(provider="tavily")
    assert denied.status == "operator_authorization_required"
    assert denied.external_requests_authorized is False

    allowed = resolve_census_flight_authority(
        provider="tavily",
        allow_paid_external_provider=True,
    )
    assert allowed.status == "authorized"
    assert allowed.external_requests_authorized is True
    assert allowed.paid_external_tool is True


def test_external_index_plan_only_performs_zero_provider_requests(monkeypatch):
    def forbidden_search(**kwargs):
        raise AssertionError("provider must not be called in plan-only mode")

    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census_comparison.search_public_web",
        forbidden_search,
    )
    observations, telemetry = _run_external_index_sources(
        provider="none",
        provider_available=True,
        external_requests_authorized=False,
        search_terms=("Data Engineer",),
        locations=("Hannover",),
        max_results=5,
        timeout_seconds=1.0,
        observed_at_utc="2026-09-27T20:40:00Z",
    )
    assert observations == []
    assert sum(
        row["provider_request_count"] for row in telemetry.values()
    ) == 0
    assert all(row["direct_board_requests"] == 0 for row in telemetry.values())


def test_incremental_metric_counts_only_novel_external_only_employers():
    report = {
        "employers": [
            {
                "company_key": "a",
                "origin_status": "novel",
                "evidence_sources": ["xing"],
            },
            {
                "company_key": "b",
                "origin_status": "known_candidate",
                "evidence_sources": ["goodjobs"],
            },
            {
                "company_key": "c",
                "origin_status": "novel",
                "evidence_sources": ["stepstone", "xing"],
            },
            {
                "company_key": "d",
                "origin_status": "novel",
                "evidence_sources": ["bundesagentur_fuer_arbeit", "meinestadt"],
            },
            {
                "company_key": "e",
                "origin_status": "novel",
                "evidence_sources": ["get_in_it", "jobvector"],
            },
        ]
    }
    metrics = _incremental_metrics(report)
    assert metrics[
        "novel_incremental_employers_vs_ba_stepstone_and_candidate_baseline"
    ] == {
        "goodjobs": 0,
        "xing": 1,
        "meinestadt": 0,
        "get_in_it": 1,
        "jobvector": 1,
    }
    assert metrics["external_source_overlap_with_ba_or_stepstone"]["xing"] == 1
    assert metrics["external_source_overlap_with_ba_or_stepstone"]["meinestadt"] == 1
    assert metrics["primary_incremental_novel_employer_count"] == 3


def test_comparison_script_has_no_write_or_direct_board_transport_authority():
    import scripts.run_job_first_employer_discovery_census_comparison as flight

    source = open(flight.__file__, encoding="utf-8").read().casefold()
    for forbidden in (
        "insert into",
        "update employer_",
        "delete from",
        "conn.commit(",
        "requests.get",
        "requests.post",
    ):
        assert forbidden not in source
