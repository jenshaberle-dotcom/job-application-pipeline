from datetime import datetime, timezone

import pytest

from scripts.product_v1_f5_mailbox_ingest import (
    MailboxIngestError,
    NormalizedMailboxObservation,
    mailbox_application_key,
    parse_normalized_mailbox_observation,
    should_discover_application,
)
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
    }
    data.update(overrides)
    return NormalizedMailboxObservation(**data)


def test_parser_rejects_raw_mail_and_secret_material() -> None:
    base = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread",
        "message_reference": "message",
        "observed_at": "2026-09-16T18:00:00+00:00",
        "subject": "Bewerbung eingegangen",
        "text_excerpt": "Vielen Dank für Ihre Bewerbung",
    }
    for forbidden in ("raw_body", "headers", "access_token"):
        payload = dict(base)
        payload[forbidden] = "secret"
        with pytest.raises(MailboxIngestError, match="raw_or_secret_mail_material_forbidden"):
            parse_normalized_mailbox_observation(payload)


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
