from datetime import date
from pathlib import Path

from scripts.run_product_v1_f5_mailbox_identity_enrichment_preflight import (
    build_input_identity,
)


SCRIPT = Path("scripts/run_product_v1_f5_mailbox_identity_enrichment_preflight.py")


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread-1",
        "message_reference": "message-1",
        "observed_at": "2026-07-01T10:00:00+00:00",
        "subject": "Ihre Bewerbung als Data Engineer",
        "text_excerpt": "Vielen Dank für Ihre Bewerbung.",
        "sender_domain": "jobs.example.com",
        "employer_name": "Example GmbH",
        "job_title": "Data Engineer",
        "source_url": None,
        "mail_direction": "inbound",
        "counterparty_domain": "jobs.example.com",
        "employer_evidence_source": "counterparty_domain_brand",
    }
    row.update(overrides)
    return row


def test_identity_preflight_groups_multiple_lifecycle_messages_for_one_application() -> None:
    rows = [
        _row(message_reference="ack"),
        _row(
            message_reference="reject",
            observed_at="2026-07-20T10:00:00+00:00",
            gmail_search_signals=["rejection"],
        ),
    ]

    grouped = build_input_identity(
        rows,
        since=date(2026, 1, 1),
        until=date(2026, 9, 17),
    )

    assert len(grouped) == 1
    identity = next(iter(grouped.values()))
    assert identity["employer_name"] == "Example GmbH"
    assert identity["job_title"] == "Data Engineer"
    assert identity["title_conflict"] is False


def test_identity_preflight_reports_missing_or_conflicting_metadata_without_inventing() -> None:
    rows = [
        _row(
            thread_reference="thread-missing",
            message_reference="missing",
            employer_name=None,
            job_title=None,
            subject="Vielen Dank für Ihre Bewerbung",
        ),
        _row(
            thread_reference="thread-a",
            message_reference="a",
            employer_name="Example GmbH",
            job_title="Data Engineer",
        ),
        _row(
            thread_reference="thread-b",
            message_reference="b",
            employer_name="Example GmbH",
            job_title="ML Engineer",
        ),
    ]

    grouped = build_input_identity(
        rows,
        since=date(2026, 1, 1),
        until=date(2026, 9, 17),
    )

    assert any(
        item["employer_name"] is None and item["job_title"] is None
        for item in grouped.values()
    )


def test_identity_enrichment_preflight_is_read_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'conn.execute("SET TRANSACTION READ ONLY")' in source
    assert '"database_writes": 0' in source
    assert '"gmail_network_requests": 0' in source
    assert '"authoritative_lifecycle_mutations": 0' in source
    assert "INSERT INTO " not in source
    assert "UPDATE " not in source
    assert "DELETE FROM " not in source
