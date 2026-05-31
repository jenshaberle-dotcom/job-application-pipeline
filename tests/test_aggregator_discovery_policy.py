from datetime import UTC, datetime, timedelta

from scripts.aggregator_discovery_policy import (
    KnownEmployerCandidate,
    candidate_recheck_decision,
    is_recheckable_gate_reason,
    normalize_company_key,
    suppress_aggregator_company,
)


def known_candidate(
    *,
    status: str = "manual_review_required",
    latest_gate_name: str | None = "professional_relevance_gate",
    latest_stop_reason: str | None = "missing professional relevance in current jobs",
    latest_reviewed_at: str | None = None,
    risk_level: str = "low",
) -> KnownEmployerCandidate:
    return KnownEmployerCandidate(
        candidate_id=7,
        company_key="finanz_informatik",
        company_name="Finanz Informatik GmbH & Co. KG",
        source_name_candidate="finanz_informatik:hannover",
        source_family_candidate="finanz_informatik",
        status=status,
        risk_level=risk_level,
        latest_gate_name=latest_gate_name,
        latest_stop_reason=latest_stop_reason,
        latest_reviewed_at=latest_reviewed_at,
    )


def test_company_key_normalization_removes_legal_suffix_noise() -> None:
    assert normalize_company_key("Finanz Informatik GmbH & Co. KG") == "finanz_informatik"
    assert normalize_company_key("HDI Group") == "hdi"


def test_unresolved_known_candidate_is_observed_as_market_evidence() -> None:
    decision = suppress_aggregator_company(
        "Finanz Informatik GmbH & Co. KG",
        [known_candidate()],
    )

    assert decision.decision == "observe_known_connector_candidate"
    assert decision.known_candidate_id == 7
    assert decision.recheck_eligible is True


def test_active_controlled_candidate_is_suppressed_but_not_rechecked() -> None:
    decision = suppress_aggregator_company(
        "Finanz Informatik",
        [known_candidate(status="active_controlled")],
    )

    assert decision.decision == "suppress_active_connector_candidate"
    assert decision.recheck_eligible is False


def test_unknown_company_remains_available_for_discovery_review() -> None:
    decision = suppress_aggregator_company("New Employer GmbH", [known_candidate()])

    assert decision.decision == "keep_for_discovery_review"
    assert decision.known_candidate_id is None


def test_recheck_reason_accepts_missing_fachliche_relevanz() -> None:
    assert is_recheckable_gate_reason(
        gate_name="professional_relevance_gate",
        stop_reason="fehlende fachliche Relevanz im aktuellen Stellenbestand",
    )


def test_hard_stop_status_is_not_automatically_rechecked() -> None:
    eligible, reason = candidate_recheck_decision(
        known_candidate(status="deprecated"),
    )

    assert eligible is False
    assert reason == "candidate status is a hard stop and is not automatically rechecked"


def test_recent_review_is_not_due_yet() -> None:
    now = datetime(2026, 5, 30, tzinfo=UTC)
    eligible, reason = candidate_recheck_decision(
        known_candidate(latest_reviewed_at=(now - timedelta(days=3)).isoformat()),
        now=now,
        interval_days=30,
    )

    assert eligible is False
    assert reason == "candidate was reviewed recently"

def test_detail_evidence_gate_is_not_generic_recheckable() -> None:
    assert not is_recheckable_gate_reason(
        gate_name="detail_evidence_gate",
        stop_reason="no concrete detail URLs",
    )


def test_temporary_technical_issue_keeps_repair_semantics() -> None:
    assert not is_recheckable_gate_reason(
        gate_name="technical_reachability_gate",
        stop_reason="temporary network issue",
    )



def test_stepstone_signal_carries_handoff_metadata() -> None:
    from scripts.aggregator_discovery_policy import (
        AggregatorCompanySignal,
        suppress_aggregator_signal,
    )

    signal = AggregatorCompanySignal(
        source_name="stepstone",
        company="Finanz Informatik GmbH & Co. KG",
        silver_job_count=3,
        first_seen_at="2026-05-01T00:00:00+00:00",
        last_seen_at="2026-05-30T00:00:00+00:00",
    )

    decision = suppress_aggregator_signal(signal, [known_candidate()])

    assert decision.aggregator_source_name == "stepstone"
    assert decision.silver_job_count == 3
    assert decision.decision == "observe_known_connector_candidate"
    assert decision.handoff_action == "queue_employer_origin_recheck"


def test_active_signal_is_suppressed_without_recheck_handoff() -> None:
    from scripts.aggregator_discovery_policy import (
        AggregatorCompanySignal,
        suppress_aggregator_signal,
    )

    signal = AggregatorCompanySignal(
        source_name="stepstone",
        company="Finanz Informatik GmbH & Co. KG",
        silver_job_count=1,
    )

    decision = suppress_aggregator_signal(
        signal,
        [known_candidate(status="active_controlled")],
    )

    assert decision.decision == "suppress_active_connector_candidate"
    assert decision.recheck_eligible is False
    assert decision.handoff_action == "suppress_from_aggregator_discovery"

def test_suppresses_employer_group_variant_for_known_candidate() -> None:
    candidate = KnownEmployerCandidate(
        candidate_id=2,
        company_key="hdi",
        company_name="HDI AG",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        status="manual_review_required",
        risk_level="medium",
        latest_gate_name="detail_evidence_gate",
        latest_stop_reason="missing detail evidence",
    )

    decision = suppress_aggregator_company("HDI Global", [candidate])

    assert decision.decision == "observe_known_connector_candidate"
    assert decision.known_candidate_id == 2
    assert decision.known_candidate_source_name == "hdi:hannover"
