from __future__ import annotations

import pytest

from src.search_intelligence.approval_gated_connector_build import (
    CONNECTOR_CANDIDATE_GATE,
    GateReview,
    connector_candidate_gate_ready,
)
from src.search_intelligence.connector_candidate_contract import (
    CONNECTOR_CANDIDATE_READY_DECISIONS,
    connector_candidate_decision_ready,
)


def _candidate_gate(
    *,
    decision: str,
    gate_status: str = "passed",
    include_spec: bool = True,
    include_detail_url: bool = True,
) -> dict[str, GateReview]:
    evidence = None
    if include_spec:
        detail_urls = ["https://example.test/jobs/data-engineer-123"] if include_detail_url else []
        evidence = {
            "connector_candidate_spec": {
                "detail_evidence": {
                    "detail_urls": detail_urls,
                }
            }
        }
    return {
        CONNECTOR_CANDIDATE_GATE: GateReview(
            gate_name=CONNECTOR_CANDIDATE_GATE,
            gate_status=gate_status,
            decision=decision,
            evidence=evidence,
        )
    }


@pytest.mark.parametrize("decision", sorted(CONNECTOR_CANDIDATE_READY_DECISIONS))
def test_connector_candidate_ready_decisions_cover_current_and_legacy_vocabulary(decision: str) -> None:
    assert connector_candidate_decision_ready(decision) is True
    assert connector_candidate_gate_ready(_candidate_gate(decision=decision)) is True


def test_connector_candidate_unknown_decision_is_not_ready() -> None:
    assert connector_candidate_decision_ready("approve_connector_registration") is False
    assert connector_candidate_gate_ready(
        _candidate_gate(decision="approve_connector_registration")
    ) is False


def test_connector_candidate_gate_must_still_be_passed() -> None:
    assert connector_candidate_gate_ready(
        _candidate_gate(decision="passed", gate_status="manual_review_required")
    ) is False


def test_connector_candidate_gate_requires_connector_spec_evidence() -> None:
    assert connector_candidate_gate_ready(
        _candidate_gate(decision="passed", include_spec=False)
    ) is False


def test_connector_candidate_gate_requires_detail_url_evidence() -> None:
    assert connector_candidate_gate_ready(
        _candidate_gate(decision="passed", include_detail_url=False)
    ) is False
