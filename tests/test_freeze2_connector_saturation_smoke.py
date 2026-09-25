from __future__ import annotations

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.connectors.generic_employer_origin import (
    GenericEmployerOriginConnector,
    GenericOriginSource,
)
from scripts.run_freeze2_connector_saturation_smoke import build_report


def _profile(source_name: str) -> SearchProfile:
    return SearchProfile(
        id=0,
        profile_name="smoke",
        source_name=source_name,
        search_location="Hannover",
        search_radius_km=None,
        offer_type=None,
        page_size=1,
    )


def test_generic_connector_supports_injected_isolated_acquirer() -> None:
    source = GenericOriginSource(
        candidate_id=7,
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://connector-smoke.invalid/example",
    )

    def loader(key: str) -> GenericOriginSource:
        assert key == "example"
        return source

    def acquirer(value: GenericOriginSource) -> AcquiredJobPage:
        assert value == source
        return AcquiredJobPage(
            requested_url="https://connector-smoke.invalid/example/jobs/one",
            final_url="https://connector-smoke.invalid/example/jobs/one",
            status_code=200,
            title="Connector Contract Smoke Job",
            html_bytes=64,
            proof_kind="synthetic_contract_smoke_only",
            discovery_source="unit_test",
            anchor_text="Connector Contract Smoke Job",
        )

    connector = GenericEmployerOriginConnector(
        company_key="example",
        candidate_loader=loader,
        job_acquirer=acquirer,
    )
    records, final_url = connector.fetch_jobs(
        _profile("generic_origin:example"),
        SearchTerm(search_term="__smoke__", id=0),
    )

    assert final_url == source.candidate_url
    assert len(records) == 1
    assert records[0].source_name == "generic_origin:example"
    assert records[0].raw_data["acquisition_evidence"]["proof_kind"] == (
        "synthetic_contract_smoke_only"
    )


def test_saturation_report_covers_full_candidate_denominator_without_persistence() -> None:
    rows = [
        {
            "id": 1,
            "company_key": "alpha",
            "company_name": "Alpha GmbH",
            "candidate_url": "https://alpha.example/jobs",
            "status": "active_controlled",
        },
        {
            "id": 2,
            "company_key": "beta",
            "company_name": "Beta GmbH",
            "candidate_url": None,
            "status": "discovery",
        },
    ]

    report = build_report(rows)

    assert report["summary"]["candidate_count"] == 2
    assert report["summary"]["registry_binding_count"] == 2
    assert report["summary"]["smoke_pass_count"] == 2
    assert report["summary"]["smoke_failure_count"] == 0
    assert report["summary"]["real_origin_url_present_count"] == 1
    assert report["summary"]["real_origin_url_missing_count"] == 1
    assert report["authority"]["synthetic_record_persistence_allowed"] is False
    assert report["boundaries"]["network_requests"] == 0
    assert report["boundaries"]["synthetic_records_persisted"] == 0
    assert report["boundaries"]["database_writes"] == 0
