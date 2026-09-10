from src.connectors.finanz_informatik import (
    CandidateLink,
    DetailPage,
    build_raw_job_record,
)


def test_fi_reference_connector_uses_generic_explicit_identifier_evidence() -> None:
    candidate = CandidateLink(
        url="https://www.f-i.de/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d",
        path="/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d",
        text="Data Platform Engineer (m/w/d) Hannover",
        location_terms=("hannover",),
        profile_terms=("data",),
        recommendation="strong_listing_candidate_for_review",
        reason="test",
    )
    detail = DetailPage(
        url=candidate.url,
        final_url="https://www.f-i.de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d",
        status_code=200,
        title="Data Platform Engineer (m/w/d) - Finanz Informatik",
        text=(
            "Data Platform Engineer Python Hannover Münster Frankfurt. "
            "Wir freuen uns auf Ihre Bewerbung unter Angabe der Kennziffer 392/B."
        ),
        html_bytes=1024,
    )

    record = build_raw_job_record(
        candidate=candidate,
        detail=detail,
        requested_listing_url="https://www.f-i.de/de/karriere/offene-stellen",
        observed_at_utc="2026-09-10T12:00:00+00:00",
    )

    metadata = record.raw_data["job"]["metadata"]
    assert metadata["structured_identifier"] == "392/B"
    assert metadata["identifier_evidence_kind"] == "explicit_label"
    assert metadata["identifier_label"] == "kennziffer"
    assert metadata["vacancy_identity_kind"] == "explicit_label_identifier"
    assert metadata["structure_field_presence"]["identifier"] is True
    assert record.raw_data["detail_evidence"]["identifier"] == "392/B"
