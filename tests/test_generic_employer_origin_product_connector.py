from __future__ import annotations

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.connectors.generic_employer_origin import GenericEmployerOriginConnector
from src.connectors.generic_employer_origin_product import (
    GenericEmployerOriginProductConnector,
    QueryProvenJob,
    QueryProvenSearchResult,
    query_semantics_status,
)
from src.connectors.generic_employer_origin_search import GenericSearchOutcome
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


def _legacy_record(title: str) -> RawJobRecord:
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


def _source(_: str):
    from src.connectors.generic_employer_origin import GenericOriginSource

    return GenericOriginSource(
        candidate_id=17,
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://example.test/careers",
    )


def _job(title: str = "Data Engineer") -> AcquiredJobPage:
    return AcquiredJobPage(
        requested_url="https://example.test/jobs/data-engineer-123",
        final_url="https://example.test/jobs/data-engineer-123",
        status_code=200,
        title=title,
        html_bytes=1234,
        proof_kind="jsonld_jobposting",
        discovery_source="targeted_search:form_detail",
        anchor_text=title,
    )


def _detail(title: str = "Data Engineer") -> dict[str, object]:
    return {
        "schema": "generic_job_detail_evidence_v1",
        "methods": ["extruct:json-ld"],
        "structured_jobposting_found": True,
        "structured_source": "json-ld",
        "title": title,
        "company_name": "Example GmbH",
        "description_excerpt": "Build Python data platforms in Hannover.",
        "description_source": "json-ld",
        "locations": ["Hannover | DE"],
        "applicant_locations": [],
        "remote": None,
        "employment_types": ["FULL_TIME"],
        "skills": ["Python"],
        "date_posted": "2026-09-09",
        "valid_through": None,
        "identifier": "123",
        "raw_html_persisted": False,
        "status_code": 200,
    }


def _query_result(title: str = "Data Engineer") -> QueryProvenSearchResult:
    return QueryProvenSearchResult(
        status="proven",
        reason="target_query_returned_jobs_control_query_returned_zero",
        jobs=(
            QueryProvenJob(
                job=_job(title),
                query="Data Engineer",
                mechanism="strict_html_form",
                detail_evidence=_detail(title),
            ),
        ),
        request_count=7,
    )


def _outcome(
    jobs: tuple[AcquiredJobPage, ...],
    *,
    mechanism: str = "strict_html_form",
    stop_reason: str = "no_next_page",
) -> GenericSearchOutcome:
    return GenericSearchOutcome(
        mechanism=mechanism,
        query="Data Engineer",
        pages_requested=1,
        detail_candidates_seen=len(jobs),
        jobs=jobs,
        exhausted=True,
        stop_reason=stop_reason,
        final_url="https://example.test/careers",
    )


def test_default_registry_uses_bronze_gated_product_connector() -> None:
    connector = create_connector("generic_origin:example")

    assert isinstance(connector, GenericEmployerOriginProductConnector)


def test_non_neutral_manual_execution_keeps_existing_connector_path(monkeypatch) -> None:
    monkeypatch.setattr(
        GenericEmployerOriginConnector,
        "fetch_jobs",
        lambda self, profile, term: ([_legacy_record("Data Engineer")], profile.source_name),
    )
    connector = GenericEmployerOriginProductConnector(company_key="example")

    records, _ = connector.fetch_jobs(_profile(), SearchTerm("manual"))

    assert len(records) == 1
    assert records[0].raw_data["bronze_admission"]["status"] == "pass"


def test_neutral_trigger_uses_company_vocabulary_not_star(monkeypatch) -> None:
    from src.connectors import generic_employer_origin_product as product

    seen: dict[str, object] = {}

    def fake_vocabulary(company_key: str) -> list[str]:
        seen["vocabulary_company"] = company_key
        return ["Platform", "Analytics"]

    monkeypatch.setattr(product, "load_company_target_terms", fake_vocabulary)

    def fake_search(*, source, target_terms, **kwargs):
        seen["source"] = source.company_key
        seen["terms"] = list(target_terms)
        seen["kwargs"] = kwargs
        return _query_result()

    monkeypatch.setattr(product, "acquire_query_proven_jobs", fake_search)
    connector = GenericEmployerOriginProductConnector(
        company_key="example",
        candidate_loader=_source,
    )

    records, final_url = connector.fetch_jobs(_profile(), SearchTerm("*"))

    assert final_url == "https://example.test/careers"
    assert seen["source"] == "example"
    assert seen["vocabulary_company"] == "example"
    assert seen["terms"] == ["Platform", "Analytics"]
    assert "*" not in seen["terms"]
    assert len(records) == 1
    record = records[0]
    assert record.raw_data["bronze_admission"]["status"] == "pass"
    assert record.raw_data["acquisition_boundary"]["detail_pages_fetched"] is True
    assert record.raw_data["acquisition_boundary"]["query_semantics_proven"] is True
    assert record.raw_data["acquisition_boundary"]["company_vocabulary_key"] == "example"
    assert record.raw_data["detail_evidence"]["status_code"] == 200
    assert record.raw_data["acquisition_evidence"]["search_term_requested"] == "Data Engineer"
    assert record.raw_data["acquisition_evidence"]["neutral_execution_trigger"] == "*"
    assert (
        record.raw_data["acquisition_evidence"]["target_vocabulary_scope"]
        == "company_vocabulary_then_canonical_fallback"
    )


def test_product_connector_drops_noncredible_query_proven_record(monkeypatch) -> None:
    from src.connectors import generic_employer_origin_product as product

    monkeypatch.setattr(product, "load_company_target_terms", lambda company_key: ["Data Engineer"])
    monkeypatch.setattr(
        product,
        "acquire_query_proven_jobs",
        lambda **kwargs: _query_result("Job"),
    )
    connector = GenericEmployerOriginProductConnector(
        company_key="example",
        candidate_loader=_source,
    )

    records, _ = connector.fetch_jobs(_profile(), SearchTerm("*"))

    assert records == []


def test_product_connector_returns_zero_when_query_semantics_are_not_proven(
    monkeypatch,
) -> None:
    from src.connectors import generic_employer_origin_product as product

    monkeypatch.setattr(product, "load_company_target_terms", lambda company_key: ["Data Engineer"])
    monkeypatch.setattr(
        product,
        "acquire_query_proven_jobs",
        lambda **kwargs: QueryProvenSearchResult(
            status="failed",
            reason="impossible_control_query_returned_jobs",
            jobs=(),
            request_count=4,
        ),
    )
    connector = GenericEmployerOriginProductConnector(
        company_key="example",
        candidate_loader=_source,
    )

    records, _ = connector.fetch_jobs(_profile(), SearchTerm("*"))

    assert records == []


def test_query_semantics_matches_live_audit_discrimination_contract() -> None:
    target = _outcome((_job(),))
    empty_control = _outcome(())

    assert query_semantics_status(
        target_outcomes=[target],
        control_outcome=empty_control,
    ) == ("proven", "target_query_returned_jobs_control_query_returned_zero")

    bad_control = _outcome((_job("Impossible control leak"),))
    assert query_semantics_status(
        target_outcomes=[target],
        control_outcome=bad_control,
    ) == ("failed", "impossible_control_query_returned_jobs")

    assert query_semantics_status(
        target_outcomes=[_outcome(())],
        control_outcome=empty_control,
    ) == ("unconfirmed_zero", "target_and_control_queries_returned_zero_jobs")
