from scripts.product_v1_f5_application_tracking_runtime import (
    build_application_tracking_payload,
)


def _application(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "application_id": 7,
        "application_key": "application:7",
        "silver_job_id": 42,
        "draft_request_id": None,
        "title": "ML Engineer",
        "company_name": "Example GmbH",
        "display_company_name": "Example GmbH",
        "source_url": "https://example.test/jobs/42",
        "prepared_at": "2026-09-16T10:00:00+00:00",
        "prepared_by": "operator",
        "submission_id": 9,
        "submitted_at": "2026-09-16T11:00:00+00:00",
        "submission_channel": "employer_portal",
        "submission_authority_kind": "operator_confirmation",
        "submission_authority_reference": "manual:42",
        "authoritative_stage": "applied",
        "authoritative_event_count": 0,
        "latest_authoritative_event_at": None,
        "attention_candidate_count": 1,
        "latest_candidate_at": "2026-09-16T12:00:00+00:00",
        "attention_status": "evidence_review_required",
    }
    row.update(overrides)
    return row


def _candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": 3,
        "matched_application_id": 7,
        "match_status": "exact",
        "candidate_class": "offer_signal",
        "source_kind": "gmail",
        "source_thread_reference": "thread-fingerprint",
        "source_message_reference": "message-fingerprint",
        "confidence": 0.99,
        "ambiguity_reason": None,
        "review_status": "unreviewed",
        "created_at": "2026-09-16T12:00:00+00:00",
        "evidence_payload": {
            "reason_code": "deterministic_offer_phrase",
            "evidence_span": "offer",
            "raw_body": "must never leave the private evidence boundary",
            "headers": {"secret": "not exposed"},
        },
    }
    row.update(overrides)
    return row


def test_candidate_offer_signal_cannot_advance_authoritative_stage() -> None:
    payload = build_application_tracking_payload(
        applications=[_application(authoritative_stage="applied")],
        candidates=[_candidate(candidate_class="offer_signal")],
    )

    application = payload["applications"][0]
    assert application["authoritative_stage"] == "applied"
    assert application["stage_authority"] == (
        "application_submission_and_confirmed_lifecycle_events"
    )
    assert application["evidence_candidates"][0]["candidate_class"] == "offer_signal"
    assert application["evidence_candidates"][0]["authority"] == "evidence_only"


def test_projection_exposes_only_bounded_normalized_evidence_fields() -> None:
    payload = build_application_tracking_payload(
        applications=[_application()],
        candidates=[_candidate()],
    )
    evidence = payload["applications"][0]["evidence_candidates"][0]["evidence"]

    assert evidence == {
        "reason_code": "deterministic_offer_phrase",
        "evidence_span": "offer",
    }
    assert "raw_body" not in evidence
    assert "headers" not in evidence


def test_unmatched_candidate_stays_outside_application_authority() -> None:
    payload = build_application_tracking_payload(
        applications=[_application(attention_candidate_count=0)],
        candidates=[
            _candidate(
                matched_application_id=None,
                match_status="unmatched",
                candidate_class="rejection",
            )
        ],
    )

    assert payload["applications"][0]["evidence_candidates"] == []
    assert payload["summary"]["unmatched_candidate_count"] == 1
    assert payload["unmatched_evidence_candidates"][0]["authority"] == "evidence_only"


def test_unavailable_projection_is_empty_and_explicit() -> None:
    payload = build_application_tracking_payload(
        applications=[], candidates=[], available=False
    )

    assert payload["available"] is False
    assert payload["summary"]["application_count"] == 0
    assert payload["boundaries"]["read_only_projection"] is True
    assert payload["boundaries"]["automatic_application_submission"] is False
