from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys

from scripts.run_product_v1_f5_mailbox_batch_preflight import preflight_rows


def _row(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_kind": "gmail",
        "mailbox_account_fingerprint": "acct",
        "thread_reference": "thread-1",
        "message_reference": "message-1",
        "observed_at": "2026-06-20T10:00:00+00:00",
        "subject": "Bewerbung als Junior Data Engineer (m/w/d)",
        "text_excerpt": "Anbei übersende ich meine Bewerbung.",
        "sender_domain": "gmail.com",
        "employer_name": "Syscrest",
        "job_title": "Junior Data Engineer (m/w/d)",
        "source_url": None,
        "mail_direction": "outbound",
        "counterparty_domain": "syscrest.com",
        "employer_evidence_source": "counterparty_domain_brand",
    }
    payload.update(overrides)
    return payload


def test_outbound_application_is_discoverable_without_submission_authority() -> None:
    result = preflight_rows([_row()])

    assert result.invalid_rows == 0
    assert result.discoverable_rows == 1
    assert result.unique_application_keys == 1
    assert result.other_rows == 0
    finding = result.findings[0]
    assert finding.candidate_class == "application_acknowledgement"
    assert finding.reason_code == "deterministic_outbound_application_sent"
    assert finding.mail_direction == "outbound"
    assert finding.counterparty_domain == "syscrest.com"


def test_generic_application_word_is_other_not_discoverable() -> None:
    result = preflight_rows(
        [
            _row(
                message_reference="tavily",
                mail_direction="inbound",
                counterparty_domain="tavily.com",
                sender_domain="tavily.com",
                employer_name="Tavily team",
                job_title=None,
                subject="You've reached your first Tavily milestone",
                text_excerpt="real time web data can support your application",
            ),
            _row(
                message_reference="cariad",
                mail_direction="inbound",
                counterparty_domain="cariad.technology",
                sender_domain="cariad.technology",
                employer_name="Haberle, Jens",
                job_title=None,
                subject="Azure Application certificate",
                text_excerpt="INTERNAL",
            ),
        ]
    )

    assert result.discoverable_rows == 0
    assert result.other_rows == 2
    assert result.review_worthy_rows == 0
    assert result.findings == ()


def test_coaching_absage_and_private_assessment_are_other() -> None:
    result = preflight_rows(
        [
            _row(
                message_reference="coaching",
                mail_direction="inbound",
                counterparty_domain="kornferry.com",
                sender_domain="kornferry.com",
                employer_name="Korn Ferry Advance",
                job_title=None,
                subject="Absage Coaching Session",
                text_excerpt="Ihre Coaching-Sitzung wurde abgesagt.",
            ),
            _row(
                message_reference="calendar",
                mail_direction="inbound",
                counterparty_domain="google.com",
                sender_domain="google.com",
                employer_name="Google Kalender",
                job_title=None,
                subject="Nach Assessment Termin im Mai schauen",
                text_excerpt="Privater Kalendertermin.",
            ),
        ]
    )

    assert result.discoverable_rows == 0
    assert result.other_rows == 2
    assert result.review_worthy_rows == 0


def test_invalid_public_payload_is_counted_and_fails_closed() -> None:
    result = preflight_rows([_row(to="jobs@example.com")])

    assert result.window_rows == 1
    assert result.valid_rows == 0
    assert result.invalid_rows == 1
    assert result.discoverable_rows == 0


def test_duplicate_evidence_is_measured_without_duplication_claim() -> None:
    first = _row()
    second = dict(first)

    result = preflight_rows([first, second])

    assert result.valid_rows == 2
    assert result.duplicate_evidence_rows == 1
    assert result.unique_application_keys == 1


def test_date_window_is_applied_before_contract_counting() -> None:
    result = preflight_rows(
        [
            _row(observed_at="2025-12-31T23:00:00+00:00"),
            _row(message_reference="2026", observed_at="2026-01-08T10:00:00+00:00"),
        ],
        since=date(2026, 1, 1),
        until=date(2026, 9, 17),
    )

    assert result.input_rows == 2
    assert result.window_rows == 1
    assert result.valid_rows == 1


def test_direct_script_entrypoint_runs_from_repository_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "mailbox.jsonl"
    report_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "run_product_v1_f5_mailbox_batch_preflight.py"),
            "--input",
            str(input_path),
            "--since",
            "2026-01-01",
            "--until",
            "2026-09-17",
            "--output",
            str(report_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "F5_MAILBOX_BATCH_PREFLIGHT=PASS" in completed.stdout
    assert "GMAIL_NETWORK_REQUESTS=0" in completed.stdout
    assert "DATABASE_WRITES=0" in completed.stdout
    assert report_path.is_file()


def test_direct_script_entrypoint_needs_no_site_packages_or_db_driver(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "mailbox-no-site-packages.jsonl"
    report_path = tmp_path / "report-no-site-packages.json"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-S",
            str(repo_root / "scripts" / "run_product_v1_f5_mailbox_batch_preflight.py"),
            "--input",
            str(input_path),
            "--since",
            "2026-01-01",
            "--until",
            "2026-09-17",
            "--output",
            str(report_path),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "F5_MAILBOX_BATCH_PREFLIGHT=PASS" in completed.stdout
    assert "GMAIL_NETWORK_REQUESTS=0" in completed.stdout
    assert "DATABASE_CONNECTIONS=0" in completed.stdout
    assert "DATABASE_WRITES=0" in completed.stdout
    assert report_path.is_file()
