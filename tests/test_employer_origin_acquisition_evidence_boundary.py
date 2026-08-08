from src.connectors.base import RawJobRecord
from src.silver.relevance import (
    build_relevance_text,
    get_accessibility_matches,
    get_role_matches,
    get_silver_decision_reason,
    get_skill_matches,
    is_relevant_for_silver,
)
from src.silver.transformer import transform_raw_job_to_silver


SOURCE_TYPE = "employer_origin_career_site"
BANGALORE_URL = (
    "https://jobs.computacenter.com/job/Bangalore-Bengaluru-%28Bangalore-"
    "Technical-Analyst-Genesys-Administrator-560025/1266548901/"
)


def generated_gate_raw_job(
    *,
    raw_job_id: int = 30950,
    source_url: str = BANGALORE_URL,
    title: str = "Technical Analyst-Genesys Administrator Job Details",
    listing_text: str = "Technical Analyst-Genesys Administrator",
    heuristic_location: str = "deutschland",
    profile_terms: list[str] | None = None,
    listing_reason: str = "Listing has profile and target/remote signals.",
) -> dict:
    return {
        "id": raw_job_id,
        "source_name": "computacenter:discovery",
        "external_job_id": "1266548901:594bd00b6602",
        "source_url": source_url,
        "raw_data": {
            "source_type": SOURCE_TYPE,
            "acquisition_boundary": {
                "generated_from_gate_evidence": True,
                "relevance_gated": True,
            },
            "result_card": {
                "title": title,
                "company_name": "Computacenter AG & Co. oHG",
                "location": heuristic_location,
                "detail_url": source_url,
            },
            "job": {
                "title": title,
                "company_name": "Computacenter AG & Co. oHG",
                "location": heuristic_location,
                "source_url": source_url,
                "profile_terms": (
                    ["data", "analyst", "sql", "ui", "bi", "ki", "ai"]
                    if profile_terms is None
                    else profile_terms
                ),
            },
            "listing_evidence": {
                "candidate_path": "/job/Bangalore-Bengaluru-Technical-Analyst/1266548901/",
                "listing_text": listing_text,
                "listing_recommendation": "strong_listing_candidate_for_review",
                "listing_reason": listing_reason,
            },
            "detail_evidence": {
                "page_title": title,
            },
        },
    }


def test_raw_job_record_moves_generated_heuristics_into_acquisition_evidence() -> None:
    raw_job = generated_gate_raw_job()
    record = RawJobRecord(
        source_name=raw_job["source_name"],
        source_url=raw_job["source_url"],
        external_job_id=raw_job["external_job_id"],
        raw_data=raw_job["raw_data"],
    )

    assert "location" not in record.raw_data["job"]
    assert "location" not in record.raw_data["result_card"]
    assert "profile_terms" not in record.raw_data["job"]
    assert record.raw_data["acquisition_evidence"] == {
        "heuristic_profile_terms": ["data", "analyst", "sql", "ui", "bi", "ki", "ai"],
        "heuristic_job_location": "deutschland",
        "heuristic_result_card_location": "deutschland",
    }

    # The source evidence remains available for audit/relevance review.
    assert record.raw_data["listing_evidence"]["listing_text"] == (
        "Technical Analyst-Genesys Administrator"
    )
    assert record.raw_data["acquisition_boundary"]["relevance_gated"] is True


def test_generated_gate_heuristics_do_not_create_silver_relevance() -> None:
    raw_job = generated_gate_raw_job()

    relevance_text = build_relevance_text(raw_job)

    assert "target remote signals" not in relevance_text
    assert "deutschland" not in relevance_text
    assert get_role_matches(raw_job) == []
    assert get_skill_matches(raw_job) == []
    assert get_accessibility_matches(raw_job) == []
    assert is_relevant_for_silver(raw_job) is False
    assert get_silver_decision_reason(raw_job) == "missing_role_or_skill_signal"


def test_generated_gate_legacy_location_is_not_canonical_silver_city() -> None:
    raw_job = generated_gate_raw_job()

    result = transform_raw_job_to_silver(raw_job)

    assert result["raw_job_id"] == 30950
    assert result["city"] is None
    assert result["country"] is None
    assert result["normalized_location"] is None
    assert result["canonical_source_type"] == SOURCE_TYPE
    assert result["canonical_key_candidate"] == (
        "computacenter ag & co. ohg :: "
        "technical analyst-genesys administrator job details"
    )


def test_source_derived_listing_text_can_still_make_generated_job_relevant() -> None:
    raw_job = generated_gate_raw_job(
        raw_job_id=30960,
        source_url=(
            "https://jobs.computacenter.com/job/Hannover-Product-Owner-"
            "Data-Platform-30159/1412345678/"
        ),
        title="Product Owner Data Platform",
        listing_text="Product Owner Data Platform Hannover",
        heuristic_location="deutschland; hannover; remote",
        profile_terms=["untrusted", "synthetic"],
        listing_reason="Connector generated reason with no source truth: remote.",
    )

    assert "product owner" in get_role_matches(raw_job)
    assert "data platform" in get_role_matches(raw_job)
    assert "hannover" in get_accessibility_matches(raw_job)
    assert is_relevant_for_silver(raw_job) is True
    assert get_silver_decision_reason(raw_job) == "relevant_role_and_accessibility"

    transformed = transform_raw_job_to_silver(raw_job)
    assert transformed["city"] is None
    assert transformed["normalized_location"] is None


def test_generated_listing_reason_remote_cannot_create_accessibility() -> None:
    raw_job = generated_gate_raw_job(
        title="Technical Administrator",
        listing_text="Technical Administrator",
        heuristic_location="",
        profile_terms=[],
        listing_reason="Listing has profile and target/remote signals.",
    )

    assert "remote" not in build_relevance_text(raw_job)
    assert get_accessibility_matches(raw_job) == []
