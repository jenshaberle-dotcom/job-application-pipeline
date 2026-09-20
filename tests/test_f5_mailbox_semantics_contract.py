from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.product_v1_f5_mailbox_ingest import (
    NormalizedMailboxObservation,
    application_kind_for_observation,
)
from src.search_intelligence.application_event_classifier import (
    _DETERMINISTIC_EVENT_SIGNALS,
    classify_application_evidence,
)


CONTRACT = Path(__file__).parents[1] / "contracts" / "f5_mailbox_semantics_v1.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _case_observation(case: dict[str, object]) -> dict[str, object]:
    value = case["observation"]
    assert isinstance(value, dict)
    return value


def test_contract_declares_public_jap_as_semantics_authority() -> None:
    contract = _contract()

    assert contract["schema_version"] == "jap.f5.mailbox_semantics_contract.v1"
    assert contract["authority"] == "job-application-pipeline"
    signal_map = contract["event_signal_runtime_lifecycle"]
    assert isinstance(signal_map, dict)
    assert set(signal_map) == set(_DETERMINISTIC_EVENT_SIGNALS)


@pytest.mark.parametrize("case", _contract()["cases"], ids=lambda case: case["id"])
def test_public_classifier_satisfies_canonical_mailbox_semantics(
    case: dict[str, object],
) -> None:
    observation = _case_observation(case)
    signals = observation.get("gmail_search_signals")
    assert isinstance(signals, list)

    result = classify_application_evidence(
        subject=str(observation.get("subject") or ""),
        text_excerpt=str(observation.get("text_excerpt") or ""),
        sender_domain=str(observation.get("sender_domain") or "") or None,
        mail_direction=str(observation.get("mail_direction") or "") or None,
        counterparty_domain=str(observation.get("counterparty_domain") or "") or None,
        deterministic_event_signals=tuple(str(item) for item in signals),
    )

    assert result.candidate_class == case["expected_public_candidate_class"]
    assert result.reason_code == case["expected_public_reason_code"]


@pytest.mark.parametrize("case", _contract()["cases"], ids=lambda case: case["id"])
def test_application_kind_semantics_satisfy_canonical_contract(
    case: dict[str, object],
) -> None:
    observation = _case_observation(case)
    normalized = NormalizedMailboxObservation(
        mailbox_account_fingerprint="contract-account",
        thread_reference=f"thread-{case['id']}",
        message_reference=f"message-{case['id']}",
        observed_at=__import__("datetime").datetime(
            2026, 9, 20, 12, 0, tzinfo=__import__("datetime").timezone.utc
        ),
        subject=str(observation.get("subject") or ""),
        text_excerpt=str(observation.get("text_excerpt") or ""),
        sender_domain=str(observation.get("sender_domain") or "") or None,
        employer_name="Example Employer",
        job_title=None,
        source_url=None,
        mail_direction=str(observation.get("mail_direction") or "inbound"),
        counterparty_domain=str(observation.get("counterparty_domain") or "") or None,
        employer_evidence_source="contract_fixture",
        gmail_search_signals=tuple(
            str(item) for item in observation.get("gmail_search_signals", [])
        ),
    )

    assert application_kind_for_observation(normalized) == case["expected_application_kind"]
