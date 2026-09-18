from datetime import date
from pathlib import Path

from scripts.run_product_v1_f5_mailbox_persistence_postwrite_proof import (
    _derive_expected,
    _validate_apply_report,
)


POSTWRITE = Path("scripts/run_product_v1_f5_mailbox_persistence_postwrite_proof.py")


def _row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread-1",
        "message_reference": "message-1",
        "observed_at": "2026-07-01T10:00:00+00:00",
        "subject": "Vielen Dank für Ihre Bewerbung",
        "text_excerpt": "Ihre Bewerbung ist eingegangen.",
        "sender_domain": "example.com",
        "employer_name": "Example GmbH",
        "job_title": "Data Engineer",
        "source_url": None,
        "mail_direction": "inbound",
        "counterparty_domain": "example.com",
        "employer_evidence_source": "counterparty_domain_brand",
    }
    payload.update(overrides)
    return payload


def test_postwrite_derivation_reconstructs_source_and_application_truth() -> None:
    candidates, applications, classes = _derive_expected(
        [
            _row(message_reference="ack"),
            _row(
                message_reference="reject",
                observed_at="2026-07-23T10:00:00+00:00",
                subject="Rückmeldung zu Ihrer Bewerbung",
                text_excerpt="Vielen Dank für Ihre Bewerbung.",
                gmail_search_signals=["rejection"],
            ),
            _row(
                message_reference="noise",
                observed_at="2026-08-01T10:00:00+00:00",
                subject="Allgemeine Nachricht",
                text_excerpt="Keine Bewerbungsinformation.",
                employer_name=None,
                job_title=None,
            ),
        ],
        since=date(2026, 1, 1),
        until=date(2026, 9, 17),
    )

    assert len(candidates) == 2
    assert len(applications) == 1
    assert classes == {"application_acknowledgement": 1, "rejection": 1}

    application = next(iter(applications.values()))
    assert application.latest_candidate_class == "rejection"
    assert application.observed_stage == "closed"
    assert application.attention_candidate_count == 2


def test_postwrite_apply_report_validation_requires_committed_evidence_only_effects() -> None:
    report = {
        "schema": "jap.f5.mailbox_persistence_apply.v1",
        "source_sha": "1" * 40,
        "input_sha256": "2" * 64,
        "plan_sha256": "3" * 64,
        "application_inserts": 9,
        "candidate_inserts": 11,
        "candidate_noops": 0,
        "candidate_supersessions": 0,
        "gmail_network_requests": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "authoritative_lifecycle_mutations": 0,
        "transaction": "committed",
    }

    _validate_apply_report(
        report,
        source_sha="1" * 40,
        input_sha256="2" * 64,
        plan_sha256="3" * 64,
        expected_application_inserts=9,
        expected_candidate_inserts=11,
    )


def test_postwrite_contract_is_read_only_and_checks_product_authority_separation() -> None:
    source = POSTWRITE.read_text(encoding="utf-8")

    assert 'conn.execute("SET TRANSACTION READ ONLY")' in source
    assert '"database_writes": 0' in source
    assert '"gmail_network_requests": 0' in source
    assert "global_authority_rows_present" in source
    assert "scoped_authority_rows_present" in source
    assert 'row["authoritative_stage"] != "prepared"' in source
    assert 'row["effective_stage_basis"] != "mailbox_observed"' in source
    assert "submission_id" in source
    assert "application_lifecycle_events" in source
    assert "application_submissions" in source
    assert "INSERT INTO " not in source
    assert "UPDATE " not in source
    assert "DELETE FROM " not in source
