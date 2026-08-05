from __future__ import annotations

from scripts.run_successfactors_connector_preview import build_preview_payload
from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.registry import create_connector
from src.connectors.successfactors import (
    EON_GERMANY_TARGET,
    MAX_DETAIL_PAGES_HARD_LIMIT,
    DetailPage,
    ListingCandidate,
    SuccessFactorsConnector,
    build_raw_job_record,
    concrete_job_url,
    extract_listing_candidates,
    job_id_from_url,
    select_listing_candidates,
)


LISTING_URL = EON_GERMANY_TARGET.listing_url
DATA_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Essen-%28Senior%29-Data-Engineer-Data-%26-AI-%28fmd%29/1414903533/"
)
OTHER_COMPANY_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Hannover-Data-Analyst-%28mwd%29/1414903999/"
)
WORKING_STUDENT_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Essen-Werkstudent-Data-%28mwd%29/1414903111/"
)
IRRELEVANT_URL = (
    "https://careers.eon.com/deutschland/job/"
    "Berlin-Sales-Manager-%28mwd%29/1414903222/"
)
OFF_HOST_URL = (
    "https://example.invalid/deutschland/job/"
    "Essen-Data-Engineer-%28mwd%29/1414903333/"
)


def listing_html() -> str:
    return (
        "<html><body>"
        f"<a href='{DATA_URL}'> (Senior) Data Engineer Data &amp; AI (f/m/d) </a>"
        f"<a href='{OTHER_COMPANY_URL}'>Data Analyst (m/w/d)</a>"
        f"<a href='{WORKING_STUDENT_URL}'>Werkstudent Data (m/w/d)</a>"
        f"<a href='{IRRELEVANT_URL}'>Sales Manager (m/w/d)</a>"
        f"<a href='{OFF_HOST_URL}'>Data Engineer (m/w/d)</a>"
        f"<a href='{DATA_URL}'>duplicate</a>"
        "</body></html>"
    )


def detail_html(
    *,
    company: str,
    title: str,
    location_metadata: str = "",
) -> str:
    return (
        "<html>"
        f"<title>{title} Job Details | E.ON</title>"
        f"<body><h1>{title}</h1>"
        f"{company} | Permanent | Part or Full time "
        "Build operational data platforms with Python, SQL, cloud and AI. "
        f"{location_metadata}"
        "</body></html>"
    )


def make_profile() -> SearchProfile:
    return SearchProfile(
        id=-1,
        profile_name="unit_test",
        source_name="successfactors:eon_germany",
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=10,
    )


def test_listing_extraction_is_same_host_relevant_and_exclusion_bounded() -> None:
    candidates = extract_listing_candidates(
        listing_html(),
        LISTING_URL,
        target=EON_GERMANY_TARGET,
        requested_term="*",
    )

    assert [candidate.url for candidate in candidates] == [
        DATA_URL,
        OTHER_COMPANY_URL,
    ]
    assert candidates[0].external_job_id == "1414903533"
    assert candidates[0].location_hint == "Essen"
    assert "data" in candidates[0].matched_terms
    assert "ai" in candidates[0].matched_terms


def test_job_url_requires_exact_host_path_and_numeric_id() -> None:
    assert concrete_job_url(DATA_URL, EON_GERMANY_TARGET)
    assert job_id_from_url(DATA_URL) == "1414903533"
    assert not concrete_job_url(OFF_HOST_URL, EON_GERMANY_TARGET)
    assert not concrete_job_url(
        "https://careers.eon.com/deutschland/go/Germany-Careers/3727101",
        EON_GERMANY_TARGET,
    )


def test_selection_hard_clamps_detail_page_limit() -> None:
    candidates = extract_listing_candidates(
        listing_html(),
        LISTING_URL,
        target=EON_GERMANY_TARGET,
    )

    assert len(select_listing_candidates(candidates, limit=99)) <= (
        MAX_DETAIL_PAGES_HARD_LIMIT
    )
    assert select_listing_candidates(candidates, limit=0) == []


def test_connector_emits_only_exact_target_employer_records() -> None:
    calls: list[str] = []

    def fake_fetcher(url: str) -> tuple[str, str, int]:
        calls.append(url)
        if url == LISTING_URL:
            return listing_html(), LISTING_URL, 200
        if url == DATA_URL:
            return (
                detail_html(
                    company="E.ON Digital Technology GmbH",
                    title="(Senior) Data Engineer Data & AI (f/m/d)",
                    location_metadata=(
                        "Location: Essen, DE Hannover, DE München, DE "
                        "Function area: IT/Digital"
                    ),
                ),
                DATA_URL,
                200,
            )
        if url == OTHER_COMPANY_URL:
            return (
                detail_html(
                    company="Other Energy GmbH",
                    title="Data Analyst (m/w/d)",
                ),
                OTHER_COMPANY_URL,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    connector = SuccessFactorsConnector(
        target_key="eon_germany",
        max_detail_pages=2,
        fetcher=fake_fetcher,
    )
    records, final_url = connector.fetch_jobs(
        make_profile(),
        SearchTerm(search_term="*", id=None),
    )

    assert final_url == LISTING_URL
    assert calls == [LISTING_URL, DATA_URL, OTHER_COMPANY_URL]
    assert len(records) == 1

    record = records[0]
    assert record.source_name == "successfactors:eon_germany"
    assert record.source_url == DATA_URL
    assert record.external_job_id == "eon_germany:1414903533"
    assert record.raw_data["source_family"] == "successfactors"
    assert record.raw_data["source_target"] == "eon_germany"
    assert record.raw_data["result_card"]["company_name"] == (
        "E.ON Digital Technology GmbH"
    )
    assert record.raw_data["result_card"]["location"] == "Essen"
    assert record.raw_data["job"]["location"] == "Essen"
    assert record.raw_data["job"]["locations"] == [
        {
            "city": "Essen",
            "country_code": "DE",
            "evidence_source": "successfactors_detail_location_field",
            "evidence_text": "Essen, DE Hannover, DE München, DE",
        },
        {
            "city": "Hannover",
            "country_code": "DE",
            "evidence_source": "successfactors_detail_location_field",
            "evidence_text": "Essen, DE Hannover, DE München, DE",
        },
        {
            "city": "München",
            "country_code": "DE",
            "evidence_source": "successfactors_detail_location_field",
            "evidence_text": "Essen, DE Hannover, DE München, DE",
        },
    ]
    assert "Data Engineer" in record.raw_data["result_card"]["title"]
    assert "Python" in record.raw_data["job"]["description"]
    boundary = record.raw_data["acquisition_boundary"]
    assert boundary["request_count"] == 3
    assert boundary["pagination_enabled"] is False
    assert boundary["browser_automation_used"] is False
    assert boundary["access_control_bypass_used"] is False
    assert boundary["provider_requests"] == 0
    assert boundary["pipeline_mutation"] is False
    detail_evidence = record.raw_data["detail_evidence"]
    assert detail_evidence["target_employer_verified"] is True
    assert detail_evidence["structured_location_count"] == 3


def test_raw_builder_does_not_infer_unlabelled_prose_locations() -> None:
    candidate = ListingCandidate(
        url=DATA_URL,
        external_job_id="1414903533",
        title_hint="(Senior) Data Engineer Data & AI (f/m/d)",
        location_hint="Essen",
        matched_terms=("data", "ai"),
        requested_term_match=False,
    )
    detail = DetailPage(
        requested_url=DATA_URL,
        final_url=DATA_URL,
        status_code=200,
        title="(Senior) Data Engineer Data & AI (f/m/d)",
        text=(
            "E.ON Digital Technology GmbH | Permanent | Part or Full time "
            "Collaborate with teams in Hannover and München."
        ),
        html_bytes=200,
    )

    record = build_raw_job_record(
        candidate=candidate,
        detail=detail,
        target=EON_GERMANY_TARGET,
        listing_url=LISTING_URL,
        observed_at_utc="2026-08-05T07:00:00+00:00",
        request_count=2,
        max_detail_pages=1,
    )

    assert record.raw_data["job"]["location"] == "Essen"
    assert record.raw_data["job"]["locations"] == []
    assert record.raw_data["detail_evidence"]["structured_location_count"] == 0


def test_registry_creates_target_without_activating_ingestion() -> None:
    connector = create_connector("successfactors:eon_germany")

    assert isinstance(connector, SuccessFactorsConnector)
    assert connector.source_name == "successfactors:eon_germany"
    assert not hasattr(connector, "activate")


def test_preview_payload_remains_review_only() -> None:
    connector = SuccessFactorsConnector(
        target_key="eon_germany",
        max_detail_pages=2,
        fetcher=lambda url: ("", url, 200),
    )
    payload = build_preview_payload(
        connector=connector,
        records=[],
        final_url=LISTING_URL,
        search_term="Data",
    )

    assert payload["artifact_type"] == "successfactors_connector_preview"
    assert payload["record_count"] == 0
    assert payload["provider_requests"] == 0
    assert payload["pipeline_mutation"] is False
    assert payload["source_activation_allowed"] is False
    assert payload["review_output_only_not_pipeline_input"] is True
    assert payload["boundary"]["max_http_requests"] == 3
    assert payload["boundary"]["database_write"] is False
