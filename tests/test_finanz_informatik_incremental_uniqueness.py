from scripts.review_finanz_informatik_incremental_uniqueness import (
    Candidate,
    EvidenceRecord,
    build_uniqueness_rows,
    candidate_from_raw_record,
    classify_uniqueness,
    token_similarity,
)


def test_token_similarity_detects_overlapping_titles() -> None:
    assert token_similarity("Product Owner OSPlus Versiegelung", "Product Owner OSPlus") >= 0.5


def test_incrementally_unique_when_no_evidence_exists() -> None:
    candidate = Candidate(
        source_candidate_url="https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
        page_title="Product Owner OSPlus Versiegelung (m/w/d)",
        recommendation="detail_candidate_supports_future_preview",
        matched_profile_terms="product owner",
        matched_location_terms="hannover",
    )

    rows = build_uniqueness_rows([candidate], [], None)

    assert rows[0].uniqueness_decision == "incrementally_unique_candidate"


def test_possible_known_elsewhere_for_partial_title_overlap() -> None:
    candidate = Candidate(
        source_candidate_url="https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
        page_title="Product Owner OSPlus Versiegelung (m/w/d)",
        recommendation="detail_candidate_supports_future_preview",
        matched_profile_terms="product owner",
        matched_location_terms="hannover",
    )
    evidence = EvidenceRecord(
        table_name="silver_jobs",
        record_id="42",
        source_name="bundesagentur_fuer_arbeit",
        source_url="https://example.test/job/42",
        title="Product Owner OSPlus",
        company_name="Finanz Informatik",
        location="Hannover",
        evidence_text="Product Owner OSPlus Finanz Informatik Hannover",
    )

    rows = build_uniqueness_rows([candidate], [evidence], None)

    assert rows[0].uniqueness_decision in {
        "likely_known_elsewhere",
        "possible_known_elsewhere_review",
    }
    assert rows[0].best_match_source_name == "bundesagentur_fuer_arbeit"


def test_db_unavailable_requires_manual_review() -> None:
    decision, reason = classify_uniqueness(
        candidate=Candidate("url", "title", "detail_candidate_supports_future_preview", "", ""),
        best_match=None,
        exact_url_match=False,
        title_similarity=0.0,
        evidence_similarity=0.0,
        db_error="no dsn",
    )

    assert decision == "manual_review_db_unavailable"
    assert "no dsn" in reason


def test_candidate_from_raw_record_uses_connector_preview_data() -> None:
    from src.connectors.base import RawJobRecord

    record = RawJobRecord(
        source_name="finanz_informatik:hannover",
        source_url="https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
        external_job_id="product-owner-osplus-versiegelung-m-w-d:e216499b2369",
        raw_data={
            "job": {
                "title": "Product Owner OSPlus Versiegelung (m/w/d)",
                "location": "hannover",
                "profile_terms": ["product owner", "sql"],
            },
            "result_card": {
                "title": "Product Owner OSPlus Versiegelung (m/w/d)",
                "location": "hannover",
            },
        },
    )

    candidate = candidate_from_raw_record(record)

    assert candidate.source_candidate_url == record.source_url
    assert candidate.page_title == "Product Owner OSPlus Versiegelung (m/w/d)"
    assert candidate.recommendation == "connector_candidate_record"
    assert candidate.matched_profile_terms == "product owner; sql"
    assert candidate.matched_location_terms == "hannover"
