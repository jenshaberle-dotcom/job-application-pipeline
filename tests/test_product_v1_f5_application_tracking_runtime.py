from scripts.product_v1_f5_application_tracking_runtime import (
    build_application_tracking_payload,
)


def _application(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "application_id": 7,
        "application_key": "application:7",
        "silver_job_id": 42,
        "draft_request_id": None,
        "discovery_kind": "jap_prepared",
        "discovered_at": "2026-09-16T10:00:00+00:00",
        "title": "ML Engineer",
        "company_name": "Example GmbH",
        "display_company_name": "Example GmbH",
        "source_url": "https://example.test/jobs/42",
        "job_identity_snapshot": {
            "title": "ML Engineer",
            "company_name": "Example GmbH",
        },
        "prepared_at": "2026-09-16T10:00:00+00:00",
        "prepared_by": "operator",
        "submission_id": 9,
        "submitted_at": "2026-09-16T11:00:00+00:00",
        "submission_channel": "employer_portal",
        "submission_authority_kind": "operator_confirmation",
        "submission_authority_reference": "manual:42",
        "authoritative_stage": "applied",
        "observed_stage": None,
        "observed_event_class": None,
        "observed_at": None,
        "observed_confidence": None,
        "effective_stage": "applied",
        "effective_stage_basis": "authoritative_fallback",
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
        "observed_at": "2026-09-16T11:55:00+00:00",
        "created_at": "2026-09-16T12:00:00+00:00",
        "evidence_payload": {
            "reason_code": "deterministic_offer_signal",
            "evidence_span": "offer",
            "raw_body": "must never leave the private evidence boundary",
            "headers": {"secret": "not exposed"},
        },
    }
    row.update(overrides)
    return row


def test_observed_offer_can_be_primary_without_rewriting_authoritative_stage() -> None:
    payload = build_application_tracking_payload(
        applications=[
            _application(
                authoritative_stage="applied",
                observed_stage="offer",
                observed_event_class="offer_signal",
                observed_at="2026-09-16T11:55:00+00:00",
                observed_confidence=0.99,
                effective_stage="offer",
                effective_stage_basis="mailbox_observed",
            )
        ],
        candidates=[_candidate(candidate_class="offer_signal")],
    )

    application = payload["applications"][0]
    assert application["authoritative_stage"] == "applied"
    assert application["observed_stage"] == "offer"
    assert application["effective_stage"] == "offer"
    assert application["effective_stage_basis"] == "mailbox_observed"
    assert application["stage_authority"] == (
        "mailbox_observed_with_separate_authoritative_correction"
    )
    assert application["evidence_candidates"][0]["authority"] == "evidence_only"
    assert application["evidence_candidates"][0]["requires_review"] is False
    assert application["attention_candidate_count"] == 0
    assert application["storage_attention_candidate_count"] == 1
    assert payload["summary"]["attention_count"] == 0


def test_ambiguous_candidate_remains_a_real_review_case() -> None:
    payload = build_application_tracking_payload(
        applications=[
            _application(
                observed_stage="closed",
                observed_event_class="rejection",
                observed_confidence=0.99,
                effective_stage="closed",
                effective_stage_basis="mailbox_observed",
                attention_candidate_count=2,
            )
        ],
        candidates=[
            _candidate(candidate_class="rejection"),
            _candidate(
                candidate_id=4,
                candidate_class="rejection",
                review_status="ambiguous",
                ambiguity_reason="multiple_application_candidates",
            ),
        ],
    )

    application = payload["applications"][0]
    assert application["effective_stage"] == "closed"
    assert application["attention_candidate_count"] == 1
    assert application["storage_attention_candidate_count"] == 2
    assert application["attention_status"] == "evidence_review_required"
    assert application["evidence_candidates"][0]["requires_review"] is False
    assert application["evidence_candidates"][1]["requires_review"] is True
    assert payload["summary"]["attention_count"] == 1


def test_multiple_qualified_signals_do_not_create_false_attention() -> None:
    payload = build_application_tracking_payload(
        applications=[
            _application(
                observed_stage="closed",
                observed_event_class="rejection",
                observed_confidence=0.99,
                effective_stage="closed",
                effective_stage_basis="mailbox_observed",
                attention_candidate_count=2,
            )
        ],
        candidates=[
            _candidate(candidate_class="application_acknowledgement"),
            _candidate(candidate_id=4, candidate_class="rejection"),
        ],
    )

    application = payload["applications"][0]
    assert application["effective_stage"] == "closed"
    assert application["attention_candidate_count"] == 0
    assert application["storage_attention_candidate_count"] == 2
    assert all(
        candidate["requires_review"] is False
        for candidate in application["evidence_candidates"]
    )
    assert payload["summary"]["attention_count"] == 0


def test_unknown_job_mailbox_application_is_supported_from_identity_snapshot() -> None:
    payload = build_application_tracking_payload(
        applications=[
            _application(
                silver_job_id=None,
                title=None,
                company_name=None,
                display_company_name=None,
                source_url=None,
                discovery_kind="mailbox_observed",
                job_identity_snapshot={
                    "job_title": "Senior Data Engineer",
                    "employer_name": "External GmbH",
                    "application_url": "https://example.test/application/123",
                    "sender_domain": "jobs.example.test",
                    "counterparty_domain": "jobs.example.test",
                    "employer_evidence_source": "counterparty_domain_brand",
                    "identity_source": "gmail_normalized_observation",
                },
                authoritative_stage="prepared",
                observed_stage="applied",
                observed_event_class="application_acknowledgement",
                effective_stage="applied",
                effective_stage_basis="mailbox_observed",
            )
        ],
        candidates=[_candidate(candidate_class="application_acknowledgement")],
    )

    application = payload["applications"][0]
    assert application["silver_job_id"] is None
    assert application["job_link_status"] == "external"
    assert application["title"] == "Senior Data Engineer"
    assert application["display_company_name"] == "External GmbH"
    assert application["source_url"] == "https://example.test/application/123"
    assert application["sender_domain"] == "jobs.example.test"
    assert application["counterparty_domain"] == "jobs.example.test"
    assert application["employer_evidence_source"] == "counterparty_domain_brand"
    assert application["identity_source"] == "gmail_normalized_observation"
    assert payload["summary"]["mailbox_discovered_count"] == 1
    assert payload["boundaries"]["unknown_job_application_supported"] is True


def test_projection_exposes_only_bounded_normalized_evidence_fields() -> None:
    payload = build_application_tracking_payload(
        applications=[_application()],
        candidates=[_candidate()],
    )
    evidence = payload["applications"][0]["evidence_candidates"][0]["evidence"]

    assert evidence == {
        "reason_code": "deterministic_offer_signal",
        "evidence_span": "offer",
    }
    assert "raw_body" not in evidence
    assert "headers" not in evidence


def test_unmatched_candidate_stays_outside_application_state() -> None:
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


def test_unsolicited_application_kind_surfaces_from_snapshot() -> None:
    payload = build_application_tracking_payload(
        applications=[
            _application(
                silver_job_id=None,
                title=None,
                company_name=None,
                display_company_name=None,
                discovery_kind="mailbox_observed",
                job_identity_snapshot={
                    "employer_name": "Example Engineering",
                    "application_kind": "unsolicited",
                    "identity_source": "gmail_normalized_observation",
                },
            )
        ],
        candidates=[],
    )

    application = payload["applications"][0]
    assert application["application_kind"] == "unsolicited"
    assert application["title"] is None


def test_unsolicited_application_kind_can_surface_from_active_evidence_fallback() -> None:
    payload = build_application_tracking_payload(
        applications=[
            _application(
                silver_job_id=None,
                title=None,
                company_name=None,
                display_company_name=None,
                discovery_kind="mailbox_observed",
                job_identity_snapshot={
                    "employer_name": "Example Engineering",
                    "identity_source": "gmail_normalized_observation",
                },
            )
        ],
        candidates=[
            _candidate(
                candidate_class="application_acknowledgement",
                evidence_payload={
                    "reason_code": "deterministic_application_acknowledgement",
                    "application_kind": "unsolicited",
                },
            )
        ],
    )

    assert payload["applications"][0]["application_kind"] == "unsolicited"
