from datetime import date
from pathlib import Path

from scripts.product_v1_f5_mailbox_ingest import (
    evidence_fingerprint,
    parse_normalized_mailbox_observation,
    source_message_identity_key,
)
from scripts.run_product_v1_f5_mailbox_persistence_preflight import (
    ActiveCandidate,
    plan_rows,
)
from src.search_intelligence.application_event_classifier import classify_application_evidence


MIGRATION = Path("db/migrations/114_application_event_candidate_source_identity.sql")
INGEST = Path("scripts/product_v1_f5_mailbox_ingest.py")


def _row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread-1",
        "message_reference": "message-1",
        "observed_at": "2026-07-01T10:00:00+00:00",
        "subject": "Vielen Dank für Ihre Bewerbung",
        "text_excerpt": "Ihre Bewerbung ist eingegangen.",
        "sender_domain": "hdi-gpc.com",
        "employer_name": "HDI",
        "job_title": "AI Engineer / Data Scientist",
        "source_url": None,
        "mail_direction": "inbound",
        "counterparty_domain": "hdi-gpc.com",
        "employer_evidence_source": "counterparty_domain_brand",
    }
    payload.update(overrides)
    return payload


def test_source_identity_is_classifier_independent_while_interpretation_changes() -> None:
    observation = parse_normalized_mailbox_observation(_row())
    acknowledgement = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
    )
    rejection = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
        deterministic_event_signals=("rejection",),
    )

    assert source_message_identity_key(observation).startswith("gmail-message:")
    assert acknowledgement.candidate_class == "application_acknowledgement"
    assert rejection.candidate_class == "rejection"
    assert evidence_fingerprint(observation, acknowledgement) != evidence_fingerprint(
        observation, rejection
    )


def test_different_messages_same_application_are_distinct_evidence_not_supersession() -> None:
    rows = [
        _row(message_reference="hdi-ack", observed_at="2026-07-01T10:00:00+00:00"),
        _row(
            message_reference="hdi-reject",
            observed_at="2026-07-23T10:00:00+00:00",
            subject="Rückmeldung zu Ihrer Bewerbung",
            text_excerpt="Vielen Dank für Ihre Bewerbung.",
            gmail_search_signals=["rejection"],
        ),
    ]

    plan = plan_rows(rows, since=date(2026, 1, 1), until=date(2026, 9, 17))

    assert plan.application_inserts == 1
    assert plan.candidate_inserts == 2
    assert plan.candidate_supersessions == 0
    assert plan.unique_source_messages == 2
    assert plan.class_counts == {"application_acknowledgement": 1, "rejection": 1}


def test_same_message_same_interpretation_is_noop() -> None:
    payload = _row()
    observation = parse_normalized_mailbox_observation(payload)
    classification = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
    )
    source_key = source_message_identity_key(observation)
    application_key = "mailbox-application:existing"
    active = {
        source_key: ActiveCandidate(
            source_identity_key=source_key,
            evidence_fingerprint=evidence_fingerprint(observation, classification),
            candidate_class=classification.candidate_class,
            application_key=application_key,
        )
    }

    plan = plan_rows(
        [payload],
        existing_application_keys={application_key},
        active_candidates=active,
    )

    assert plan.application_inserts == 0
    assert plan.candidate_inserts == 0
    assert plan.candidate_noops == 1
    assert plan.candidate_supersessions == 0


def test_same_message_reclassification_supersedes_one_active_interpretation() -> None:
    payload = _row(gmail_search_signals=["rejection"])
    observation = parse_normalized_mailbox_observation(payload)
    current = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
        deterministic_event_signals=("rejection",),
    )
    previous = classify_application_evidence(
        subject=observation.subject,
        text_excerpt=observation.text_excerpt,
        sender_domain=observation.sender_domain,
    )
    source_key = source_message_identity_key(observation)
    application_key = "mailbox-application:existing"
    active = {
        source_key: ActiveCandidate(
            source_identity_key=source_key,
            evidence_fingerprint=evidence_fingerprint(observation, previous),
            candidate_class=previous.candidate_class,
            application_key=application_key,
        )
    }

    plan = plan_rows(
        [payload],
        existing_application_keys={application_key},
        active_candidates=active,
    )

    assert current.candidate_class == "rejection"
    assert plan.application_inserts == 0
    assert plan.candidate_inserts == 0
    assert plan.candidate_noops == 0
    assert plan.candidate_supersessions == 1


def test_other_mail_is_not_planned_for_persistence() -> None:
    plan = plan_rows(
        [
            _row(
                subject="Allgemeine Nachricht",
                text_excerpt="Keine Bewerbungsinformation.",
                employer_name=None,
                job_title=None,
            )
        ]
    )

    assert plan.persistence_candidate_rows == 0
    assert plan.skipped_other_rows == 1
    assert plan.application_inserts == 0
    assert plan.candidate_inserts == 0


def test_ingest_serializes_first_seen_source_identity_and_preserves_existing_match() -> None:
    source = INGEST.read_text(encoding="utf-8")

    assert "pg_advisory_xact_lock(hashtext(%s))" in source
    assert "application.application_key AS matched_application_key" in source
    assert "FOR UPDATE OF candidate" in source
    assert 'resolved_application_key = str(matched_key)' in source


def test_migration_enforces_one_active_interpretation_per_source_message() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS source_identity_key TEXT" in sql
    assert "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE" in sql
    assert "ADD COLUMN IF NOT EXISTS supersedes_candidate_id BIGINT" in sql
    assert "DROP CONSTRAINT IF EXISTS uq_application_event_candidate_evidence" in sql
    assert "uq_application_event_candidate_active_source" in sql
    assert "WHERE is_active" in sql
    assert "fk_application_event_candidate_supersedes_same_source" in sql
    assert "candidate.is_active" in sql
