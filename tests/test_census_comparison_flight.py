import pytest

from scripts.run_job_first_employer_discovery_census_comparison import (
    RuntimeProfileIntent,
    _external_location_signals,
    _incremental_metrics,
    _profile_intents_from_rows,
    _run_control_sources,
    _run_external_index_sources,
)
from src.connectors.base import SearchProfile
from src.search_intelligence.census_flight_authority import (
    resolve_census_flight_authority,
)
from src.search_intelligence.public_web_search import (
    PublicSearchResponse,
    PublicSearchResult,
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


def test_profile_intents_preserve_all_active_terms_and_source_specific_profiles():
    rows = [
        {
            "id": 1,
            "profile_name": "ba_data_engineer_30629_50km",
            "source_name": "bundesagentur_fuer_arbeit",
            "search_location": "30629",
            "search_radius_km": 50,
            "offer_type": 1,
            "page_size": 25,
            "search_term": term,
        }
        for term in (
            "Agentic AI",
            "AI Architect",
            "Data Engineer",
            "ML Engineer",
            "MLOps Engineer",
        )
    ] + [
        {
            "id": 2,
            "profile_name": "stepstone_data_engineer_hannover",
            "source_name": "stepstone",
            "search_location": "Hannover",
            "search_radius_km": None,
            "offer_type": None,
            "page_size": 25,
            "search_term": term,
        }
        for term in (
            "AI Platform Engineer",
            "Analytics Engineer",
            "Data Platform Engineer",
            "Machine Learning Engineer",
        )
    ]

    intents = _profile_intents_from_rows(rows)
    assert len(intents) == 2

    ba = next(
        item
        for item in intents
        if item.profile.source_name == "bundesagentur_fuer_arbeit"
    )
    stepstone = next(
        item for item in intents if item.profile.source_name == "stepstone"
    )

    assert len(ba.search_terms) == 5
    assert set(ba.search_terms) == {
        "Agentic AI",
        "AI Architect",
        "Data Engineer",
        "ML Engineer",
        "MLOps Engineer",
    }
    assert ba.profile.search_location == "30629"
    assert ba.profile.search_radius_km == 50
    assert ba.profile.offer_type == 1
    assert ba.profile.page_size == 25

    assert len(stepstone.search_terms) == 4
    assert stepstone.profile.search_location == "Hannover"
    assert stepstone.profile.search_radius_km is None
    assert stepstone.profile.offer_type is None
    assert stepstone.profile.page_size == 25



def test_external_market_intents_canonicalize_local_and_remote_profiles():
    intents = (
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=1,
                profile_name="ba_data_engineer_30629_50km",
                source_name="bundesagentur_fuer_arbeit",
                search_location="30629",
                search_radius_km=50,
                offer_type=1,
                page_size=10,
            ),
            search_terms=("Data Engineer",),
        ),
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=2,
                profile_name="ba_data_engineering_remote_nationwide_review",
                source_name="bundesagentur_fuer_arbeit",
                search_location=None,
                search_radius_km=None,
                offer_type=1,
                page_size=10,
            ),
            search_terms=("Data Engineer", "Analytics Engineer"),
        ),
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=3,
                profile_name="stepstone_data_engineer_hannover",
                source_name="stepstone",
                search_location="Hannover",
                search_radius_km=None,
                offer_type=None,
                page_size=25,
            ),
            search_terms=("Machine Learning Engineer",),
        ),
    )

    assert _external_location_signals(intents) == (
        "Hannover",
        "Deutschland remote",
    )


def test_external_market_intents_do_not_duplicate_postcode_and_hannover():
    intents = (
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=1,
                profile_name="ba_data_engineer_30629_50km",
                source_name="bundesagentur_fuer_arbeit",
                search_location="30629",
                search_radius_km=50,
                offer_type=1,
                page_size=10,
            ),
            search_terms=("Data Engineer",),
        ),
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=2,
                profile_name="stepstone_data_engineer_hannover",
                source_name="stepstone",
                search_location="Hannover",
                search_radius_km=None,
                offer_type=None,
                page_size=25,
            ),
            search_terms=("Analytics Engineer",),
        ),
    )

    assert _external_location_signals(intents) == ("Hannover",)

def test_control_sources_receive_their_own_profile_authority(monkeypatch):
    calls: list[tuple[str, str | None, int | None, str]] = []

    class FakeBA:
        def fetch_jobs(self, profile, search_term):
            calls.append(
                (
                    profile.source_name,
                    profile.search_location,
                    profile.search_radius_km,
                    search_term.search_term,
                )
            )
            return [], "https://example.invalid/ba"

    class FakeStepStone:
        def fetch_jobs(self, profile, search_term):
            calls.append(
                (
                    profile.source_name,
                    profile.search_location,
                    profile.search_radius_km,
                    search_term.search_term,
                )
            )
            return [], "https://example.invalid/stepstone"

    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census_comparison."
        "BundesagenturConnector",
        FakeBA,
    )
    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census_comparison."
        "StepStoneConnector",
        FakeStepStone,
    )

    intents = (
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=1,
                profile_name="ba",
                source_name="bundesagentur_fuer_arbeit",
                search_location="30629",
                search_radius_km=50,
                offer_type=1,
                page_size=25,
            ),
            search_terms=("Data Engineer", "ML Engineer"),
        ),
        RuntimeProfileIntent(
            profile=SearchProfile(
                id=2,
                profile_name="stepstone",
                source_name="stepstone",
                search_location="Hannover",
                search_radius_km=None,
                offer_type=None,
                page_size=25,
            ),
            search_terms=("Analytics Engineer",),
        ),
    )

    observations, telemetry = _run_control_sources(
        profile_intents=intents,
        observed_at_utc="2026-09-28T06:30:00Z",
    )
    assert observations == []
    assert calls == [
        ("bundesagentur_fuer_arbeit", "30629", 50, "Data Engineer"),
        ("bundesagentur_fuer_arbeit", "30629", 50, "ML Engineer"),
        ("stepstone", "Hannover", None, "Analytics Engineer"),
    ]
    assert telemetry["bundesagentur_fuer_arbeit"]["fetch_invocations"] == 2
    assert telemetry["stepstone"]["fetch_invocations"] == 1


def test_external_index_plan_only_preserves_full_raster_with_zero_requests(monkeypatch):
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
        search_terms=("Data Engineer", "ML Engineer", "MLOps Engineer"),
        locations=("30629", "Hannover"),
        max_results=5,
        max_external_requests=1,
        timeout_seconds=1.0,
        observed_at_utc="2026-09-28T06:30:00Z",
    )
    assert observations == []
    assert sum(
        row["provider_request_count"] for row in telemetry.values()
    ) == 0
    assert sum(row["query_count"] for row in telemetry.values()) == 30
    assert all(row["full_raster_preserved"] is True for row in telemetry.values())
    assert all(row["direct_board_requests"] == 0 for row in telemetry.values())


def test_paid_budget_refuses_full_raster_before_first_provider_request(monkeypatch):
    calls = {"count": 0}

    def forbidden_search(**kwargs):
        calls["count"] += 1
        raise AssertionError("budget gate must stop before provider request 1")

    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census_comparison.search_public_web",
        forbidden_search,
    )

    with pytest.raises(RuntimeError, match="refusing to truncate search intent"):
        _run_external_index_sources(
            provider="tavily",
            provider_available=True,
            external_requests_authorized=True,
            search_terms=("Data Engineer", "ML Engineer"),
            locations=("Hannover",),
            max_results=5,
            max_external_requests=1,
            timeout_seconds=1.0,
            observed_at_utc="2026-09-28T06:30:00Z",
        )
    assert calls["count"] == 0


def test_comparison_runner_contains_no_hidden_search_term_or_location_limit():
    import scripts.run_job_first_employer_discovery_census_comparison as flight

    source = open(flight.__file__, encoding="utf-8").read()
    assert "--max-terms" not in source
    assert "--max-locations" not in source
    assert "LIMIT %s" not in source
    assert "refusing to truncate search intent" in source


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
    assert metrics["primary_incremental_novel_employer_count"] == 2


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
        "run_origin_source_discovery_agent",
        "src.connectors.registry",
    ):
        assert forbidden not in source


def test_external_index_telemetry_separates_shape_rejection_from_acceptance(
    monkeypatch,
) -> None:
    def fake_search(*, provider, query, max_results, timeout_seconds):
        if query.startswith("site:xing.com "):
            return PublicSearchResponse(
                provider="tavily",
                query=query,
                status="ok",
                request_count=1,
                results=(
                    PublicSearchResult(
                        provider="tavily",
                        query=query,
                        url=(
                            "https://www.xing.com/jobs/"
                            "hannover-data-engineer-germany-158080692"
                        ),
                        title="Data Engineer - Germany in Hannover | XING Jobs",
                        snippet=(
                            "Hornetsecurity GmbH · Hannover · Hybrid · Data Engineer"
                        ),
                    ),
                    PublicSearchResult(
                        provider="tavily",
                        query=query,
                        url="https://www.xing.com/jobs/data-engineer-jobs-in-hannover",
                        title="Data Engineer Jobs in Hannover",
                        snippet="57 Data Engineer Jobs in Hannover",
                    ),
                ),
            )
        return PublicSearchResponse(
            provider="tavily",
            query=query,
            status="zero_yield",
            request_count=1,
            results=(),
        )

    monkeypatch.setattr(
        "scripts.run_job_first_employer_discovery_census_comparison.search_public_web",
        fake_search,
    )

    observations, telemetry = _run_external_index_sources(
        provider="tavily",
        provider_available=True,
        external_requests_authorized=True,
        search_terms=("Data Engineer",),
        locations=("Hannover",),
        max_results=5,
        max_external_requests=5,
        timeout_seconds=1.0,
        observed_at_utc="2026-09-28T08:55:00Z",
    )

    xing = telemetry["xing"]
    assert len(observations) == 1
    assert xing["provider_results_seen"] == 2
    assert xing["accepted_observations"] == 1
    assert xing["rejected_provider_results"] == 1
    assert xing["rejection_reason_counts"] == {"unexpected_path": 1}
