from __future__ import annotations

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.generic_employer_origin import GenericEmployerOriginConnector
from src.connectors.generic_employer_origin_product import (
    GenericEmployerOriginProductConnector,
)
from src.connectors.registry import create_connector


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


def _record(title: str) -> RawJobRecord:
    url = "https://example.test/jobs/data-engineer-123"
    return RawJobRecord(
        source_name="generic_origin:example",
        source_url=url,
        external_job_id="data-engineer-123",
        raw_data={
            "source_family": "generic_origin",
            "result_card": {
                "title": title,
                "company_name": "Example GmbH",
                "detail_url": url,
            },
            "job": {
                "title": title,
                "company_name": "Example GmbH",
                "source_url": url,
            },
            "acquisition_evidence": {
                "proof_kind": "jsonld_jobposting",
                "candidate_id": 17,
                "generic_layer_product": True,
            },
        },
    )


def test_default_registry_uses_bronze_gated_product_connector() -> None:
    connector = create_connector("generic_origin:example")

    assert isinstance(connector, GenericEmployerOriginProductConnector)


def test_product_connector_drops_noncredible_record_without_invalidating_source(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        GenericEmployerOriginConnector,
        "fetch_jobs",
        lambda self, profile, term: ([_record("Job")], profile.source_name),
    )
    connector = GenericEmployerOriginProductConnector(company_key="example")

    records, _ = connector.fetch_jobs(_profile(), SearchTerm("*"))

    assert records == []


def test_product_connector_stamps_admissible_record(monkeypatch) -> None:
    monkeypatch.setattr(
        GenericEmployerOriginConnector,
        "fetch_jobs",
        lambda self, profile, term: ([_record("Data Engineer")], profile.source_name),
    )
    connector = GenericEmployerOriginProductConnector(company_key="example")

    records, _ = connector.fetch_jobs(_profile(), SearchTerm("*"))

    assert len(records) == 1
    assert records[0].raw_data["bronze_admission"]["status"] == "pass"
    assert records[0].raw_data["bronze_admission"]["source_validity_is_separate"] is True
