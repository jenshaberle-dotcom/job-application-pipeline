from __future__ import annotations

from src.connectors import generic_employer_origin as generic
from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.employer_origin_acquisition import AcquiredJobPage


def _source(_: str) -> generic.GenericOriginSource:
    return generic.GenericOriginSource(
        candidate_id=17,
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://example.test/careers",
    )


def _profile() -> SearchProfile:
    return SearchProfile(
        id=1,
        profile_name="generic_origin__example",
        source_name="generic_origin:example",
        search_location="Hannover",
        search_radius_km=50,
        offer_type=1,
        page_size=1,
    )


def test_generic_connector_emits_proven_job_as_raw_record(monkeypatch) -> None:
    job = AcquiredJobPage(
        requested_url="https://example.test/jobs/data-engineer-123",
        final_url="https://example.test/jobs/data-engineer-123",
        status_code=200,
        title="Data Engineer",
        html_bytes=1234,
        proof_kind="jsonld_jobposting",
        discovery_source="anchor_detail",
        anchor_text="Data Engineer",
    )
    monkeypatch.setattr(generic, "acquire_one_generic_job", lambda source: job)

    connector = generic.GenericEmployerOriginConnector(
        company_key="example",
        candidate_loader=_source,
    )
    records, final_url = connector.fetch_jobs(_profile(), SearchTerm("jobs"))

    assert final_url == "https://example.test/careers"
    assert len(records) == 1
    record = records[0]
    assert record.source_name == "generic_origin:example"
    assert record.source_url == job.final_url
    assert record.raw_data["job"]["title"] == "Data Engineer"
    assert record.raw_data["job"]["company_name"] == "Example GmbH"
    assert record.raw_data["acquisition_evidence"]["proof_kind"] == "jsonld_jobposting"
    assert record.raw_data["acquisition_evidence"]["generic_layer_product"] is True


def test_generic_connector_returns_zero_when_current_proof_job_disappears(monkeypatch) -> None:
    monkeypatch.setattr(generic, "acquire_one_generic_job", lambda source: None)

    connector = generic.GenericEmployerOriginConnector(
        company_key="example",
        candidate_loader=_source,
    )
    records, final_url = connector.fetch_jobs(_profile(), SearchTerm("jobs"))

    assert records == []
    assert final_url == "https://example.test/careers"
    assert connector.capabilities.supports_full_fetch is False
