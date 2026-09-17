from __future__ import annotations

from datetime import date

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
