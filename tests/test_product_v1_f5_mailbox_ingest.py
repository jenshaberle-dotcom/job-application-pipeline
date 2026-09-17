from datetime import datetime, timezone

import pytest

from scripts.product_v1_f5_mailbox_ingest import (
    MailboxIngestError,
    NormalizedMailboxObservation,
    mailbox_application_key,
    parse_normalized_mailbox_observation,
    should_discover_application,
)
from scripts.run_product_v1_f5_mailbox_batch_preflight import preflight_rows
from src.search_intelligence.application_event_classifier import (
    classify_application_evidence,
)


def _observation(**overrides: object) -> NormalizedMailboxObservation:
    data: dict[str, object] = {
        "mailbox_account_fingerprint": "acct-fingerprint",
        "thread_reference": "thread-fingerprint",
        "message_reference": "message-fingerprint",
        "observed_at": datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc),
        "subject": "Vielen Dank für Ihre Bewerbung als Senior Data Engineer",
        "text_excerpt": "Ihre Bewerbung ist eingegangen.",
        "sender_domain": "example.com",
        "employer_name": "Example GmbH",
        "job_title": "Senior Data Engineer",
        "source_url": None,
        "mail_direction": "inbound",
        "counterparty_domain": "example.com",
        "employer_evidence_source": "counterparty_domain_brand",
    }
    data.update(overrides)
    return NormalizedMailboxObservation(**data)


def test_parser_rejects_raw_mail_secret_and_recipient_material() -> None:
    base = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread",
        "message_reference": "message",
        "observed_at": "2026-09-16T18:00:00+00:00",
        "subject": "Bewerbung eingegangen",
        "text_excerpt": "Vielen Dank für Ihre Bewerbung",
    }
    for forbidden in (
        "raw_body",
        "headers",
        "access_token",
        "to",
        "recipient",
        "recipient_address",
        "from_address",
    ):
        payload = dict(base)
        payload[forbidden] = "secret@example.test"
        with pytest.raises(MailboxIngestError, match="raw_or_secret_mail_material_forbidden"):
            parse_normalized_mailbox_observation(payload)


def test_parser_preserves_bounded_direction_and_counterparty_provenance() -> None:
    parsed = parse_normalized_mailbox_observation(
        {
            "source_kind": "gmail",
            "mailbox_account_fingerprint": "acct",
            "thread_reference": "thread",
            "message_reference": "message",
            "observed_at": "2026-06-20T12:00:00+00:00",
            "subject": "Bewerbung als Junior Data Engineer (m/w/d)",
            "text_excerpt": "Anbei meine Bewerbung.",
            "sender_domain": "gmail.com",
            "employer_name": "Example Employer",
            "job_title": "Junior Data Engineer (m/w/d)",
            "mail_direction": "outbound",
            "counterparty_domain": "jobs.example-employer.com",
            "employer_evidence_source": "counterparty_domain_brand",
        }
    )

    assert parsed.mail_direction == "outbound"
    assert parsed.counterparty_domain == "jobs.example-employer.com"
    assert parsed.employer_evidence_source == "counterparty_domain_brand"
    assert parsed.sender_domain == "gmail.com"


def test_parser_accepts_only_bounded_gmail_search_signal_classes() -> None:
    base = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread",
        "message_reference": "message",
        "observed_at": "2026-06-21T12:00:00+00:00",
        "subject": "Update zu Ihrer Bewerbung",
        "text_excerpt": "Vielen Dank für Ihre Bewerbung.",
        "sender_domain": "example.com",
        "mail_direction": "inbound",
        "counterparty_domain": "example.com",
    }
    parsed = parse_normalized_mailbox_observation(
        dict(base, gmail_search_signals=["rejection", "assessment_request"])
    )
    assert parsed.gmail_search_signals == ("rejection", "assessment_request")

    with pytest.raises(MailboxIngestError, match="gmail_search_signals_must_be_list"):
        parse_normalized_mailbox_observation(
            dict(base, gmail_search_signals="rejection")
        )
    with pytest.raises(MailboxIngestError, match="invalid_gmail_search_signal"):
        parse_normalized_mailbox_observation(
            dict(base, gmail_search_signals=["made_up_transition"])
        )
    with pytest.raises(MailboxIngestError, match="duplicate_gmail_search_signal"):
        parse_normalized_mailbox_observation(
            dict(base, gmail_search_signals=["rejection", "rejection"])
        )


def test_outbound_requires_domain_not_recipient_address() -> None:
    base = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread",
        "message_reference": "message",
        "observed_at": "2026-06-20T12:00:00+00:00",
        "subject": "Bewerbung als Junior Data Engineer",
        "text_excerpt": "Anbei meine Bewerbung.",
        "sender_domain": "gmail.com",
        "mail_direction": "outbound",
    }
    with pytest.raises(MailboxIngestError, match="required_text_missing"):
        parse_normalized_mailbox_observation(base)

    leaking = dict(base, counterparty_domain="jobs@example-employer.com")
    with pytest.raises(MailboxIngestError, match="invalid_bounded_domain"):
        parse_normalized_mailbox_observation(leaking)


def test_application_identity_is_independent_of_jap_job_and_stable_across_threads() -> None:
    first = _observation(thread_reference="thread-a")
    second = _observation(thread_reference="thread-b")

    assert mailbox_application_key(first) == mailbox_application_key(second)
    assert mailbox_application_key(first).startswith("mailbox-application:")


def test_thread_identity_is_fallback_when_job_identity_is_incomplete() -> None:
    first = _observation(employer_name=None, job_title=None, thread_reference="thread-a")
    second = _observation(employer_name=None, job_title=None, thread_reference="thread-b")

    assert mailbox_application_key(first) != mailbox_application_key(second)


def test_clear_application_acknowledgement_can_discover_unknown_application() -> None:
    result = classify_application_evidence(
        subject="Vielen Dank für Ihre Bewerbung",
        text_excerpt="Ihre Bewerbung ist eingegangen.",
        sender_domain="example.com",
    )

    assert result.candidate_class == "application_acknowledgement"
    assert should_discover_application(result) is True


def test_outbound_application_evidence_can_discover_without_submission_authority() -> None:
    result = classify_application_evidence(
        subject="Bewerbung als Junior Data Engineer (m/w/d)",
        text_excerpt="Anbei meine Bewerbung.",
        sender_domain="gmail.com",
        mail_direction="outbound",
        counterparty_domain="example-employer.com",
    )

    assert result.reason_code == "deterministic_outbound_application_sent"
    assert result.authority == "evidence_only"
    assert should_discover_application(result) is True


def test_generic_recruiter_contact_does_not_create_new_application_by_itself() -> None:
    result = classify_application_evidence(
        subject="Recruiter contact",
        text_excerpt="Ich würde gern ein kurzes Gespräch führen.",
        sender_domain="example.com",
    )

    assert result.candidate_class == "recruiter_contact"
    assert should_discover_application(result) is False


def test_ambiguous_or_other_evidence_cannot_create_application() -> None:
    ambiguous = classify_application_evidence(
        subject="Interview und leider nicht",
        text_excerpt="Vorstellungsgespräch Absage",
        sender_domain="example.com",
    )
    other = classify_application_evidence(
        subject="Hello",
        text_excerpt="Allgemeine Nachricht",
        sender_domain="example.com",
    )

    assert should_discover_application(ambiguous) is False
    assert should_discover_application(other) is False


def test_batch_preflight_consumes_bounded_signal_without_body_material() -> None:
    result = preflight_rows(
        [
            {
                "source_kind": "gmail",
                "mailbox_account_fingerprint": "acct",
                "thread_reference": "cap-thread",
                "message_reference": "cap-message",
                "observed_at": "2026-06-21T10:02:08+00:00",
                "subject": "Capgemini - Rückmeldung zu deinem Bewerbungsprozess",
                "text_excerpt": (
                    "Hallo Jens, vielen Dank für deine Bewerbung für die Position als "
                    "(Senior) Azure Data Engineer (w/m/d) sowie das entgegengebrachte Interesse"
                ),
                "sender_domain": "capgemini.com",
                "employer_name": "Capgemini",
                "job_title": "(Senior) Azure Data Engineer (w/m/d)",
                "mail_direction": "inbound",
                "counterparty_domain": "capgemini.com",
                "employer_evidence_source": "counterparty_domain_brand",
                "gmail_search_signals": ["rejection"],
            }
        ]
    )

    assert result.invalid_rows == 0
    assert result.ambiguous_rows == 0
    assert result.discoverable_rows == 1
    assert result.class_counts == {"rejection": 1}
    assert result.findings[0].candidate_class == "rejection"


def test_batch_preflight_is_read_only_contract_surface() -> None:
    result = preflight_rows(
        [
            {
                "source_kind": "gmail",
                "mailbox_account_fingerprint": "acct",
                "thread_reference": "thread-outbound",
                "message_reference": "message-outbound",
                "observed_at": "2026-06-20T12:00:00+00:00",
                "subject": "Bewerbung als Junior Data Engineer (m/w/d)",
                "text_excerpt": "Anbei meine Bewerbung.",
                "sender_domain": "gmail.com",
                "employer_name": "Example Employer",
                "job_title": "Junior Data Engineer (m/w/d)",
                "mail_direction": "outbound",
                "counterparty_domain": "example-employer.com",
                "employer_evidence_source": "counterparty_domain_brand",
            },
            {
                "source_kind": "gmail",
                "mailbox_account_fingerprint": "acct",
                "thread_reference": "thread-noise",
                "message_reference": "message-noise",
                "observed_at": "2026-03-24T12:00:00+00:00",
                "subject": "Absage Coaching Session",
                "text_excerpt": "Ihre Coaching-Sitzung wurde abgesagt.",
                "sender_domain": "kornferry.com",
                "employer_name": "Korn Ferry Advance",
                "job_title": None,
                "mail_direction": "inbound",
                "counterparty_domain": "kornferry.com",
            },
        ]
    )

    assert result.invalid_rows == 0
    assert result.discoverable_rows == 1
    assert result.other_rows == 1
    assert result.unique_application_keys == 1
