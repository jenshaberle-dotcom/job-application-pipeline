from __future__ import annotations

from dataclasses import replace

from src.search_intelligence.browser_protected_origin_architecture import (
    CollectorCapabilityEvidence,
    OriginTruthEvidence,
    evaluate_browser_protected_origin,
)

EON_URL = (
    "https://www.eon.com/de/ueber-uns/karriere/"
    "unsere-gesellschaften/digital-technology.html"
)
NOW = "2026-08-04T10:00:00+00:00"
DIGEST = "a" * 64


def _origin(**changes: object) -> OriginTruthEvidence:
    baseline = OriginTruthEvidence(
        schema_version="1.0",
        evidence_id="origin-eon-001",
        company_key="e_on_digital_technology",
        normalized_url=EON_URL,
        evidence_source="operator_attestation",
        observed_at="2026-08-04T09:00:00+00:00",
        expires_at="2026-09-03T09:00:00+00:00",
        verifier_identity="operator:jens",
        verifier_version="operator-attestation/1.0",
        requested_url=EON_URL,
        final_url=EON_URL,
        canonical_url=EON_URL,
        page_title="E.ON Digital Technology | Careers",
        observed_entity_tokens=("digital", "technology"),
        observed_career_signals=("karriere",),
        content_sha256=DIGEST,
        screenshot_sha256="b" * 64,
        operator_approval_token="approval:eon:2026-08-04",
        challenge_encountered=False,
        automation_interacted_with_challenge=False,
        automation_techniques=("standard_browser_navigation",),
    )
    return replace(baseline, **changes)


def _collector(**changes: object) -> CollectorCapabilityEvidence:
    baseline = CollectorCapabilityEvidence(
        schema_version="1.0",
        evidence_id="collector-eon-001",
        normalized_url=EON_URL,
        observed_at="2026-08-04T09:05:00+00:00",
        expires_at="2026-08-11T09:05:00+00:00",
        collector_identity="requests-origin-probe",
        collector_version="1.0",
        requested_url=EON_URL,
        final_url=EON_URL,
        status_code=403,
        reachable=False,
        challenge_detected=True,
        failure_class="access_control_challenge",
        side_effect_free=True,
        provider_requests=0,
        pipeline_mutation=False,
    )
    return replace(baseline, **changes)


def _evaluate(
    *,
    origin: OriginTruthEvidence | None = None,
    collector: CollectorCapabilityEvidence | None = None,
):
    return evaluate_browser_protected_origin(
        company_key="e_on_digital_technology",
        operator_url=EON_URL,
        required_entity_tokens=("digital", "technology"),
        origin_evidence=_origin() if origin is None else origin,
        collector_evidence=_collector() if collector is None else collector,
        now=NOW,
    )


def test_operator_attestation_separates_origin_truth_from_blocked_collection() -> None:
    decision = _evaluate()

    assert decision.decision == "origin_verified_collection_blocked"
    assert decision.origin_truth_state == "verified"
    assert decision.collection_state == "blocked_by_access_control"
    assert decision.verification_basis == "operator_attestation"
    assert decision.verified_url == EON_URL
    assert decision.collection_feasibility_proven is False
    assert decision.source_activation_allowed is False
    assert decision.provider_requests == 0
    assert decision.pipeline_mutation is False
    assert "selected_deterministic_operator_url" not in decision.to_json().values()


def test_403_alone_never_establishes_origin_truth() -> None:
    decision = evaluate_browser_protected_origin(
        company_key="e_on_digital_technology",
        operator_url=EON_URL,
        required_entity_tokens=("digital", "technology"),
        origin_evidence=None,
        collector_evidence=_collector(),
        now=NOW,
    )

    assert decision.decision == "operator_review_required"
    assert decision.origin_truth_state == "unverified"
    assert decision.collection_state == "blocked_by_access_control"
    assert decision.verified_url is None


def test_browser_verifier_must_stop_when_challenge_is_encountered() -> None:
    evidence = _origin(
        evidence_source="browser_observation",
        operator_approval_token=None,
        challenge_encountered=True,
    )

    decision = _evaluate(origin=evidence)

    assert decision.decision == "operator_review_required"
    assert any("must stop" in reason for reason in decision.reasons)


def test_automated_challenge_interaction_is_rejected() -> None:
    evidence = _origin(
        evidence_source="browser_observation",
        operator_approval_token=None,
        automation_interacted_with_challenge=True,
    )

    decision = _evaluate(origin=evidence)

    assert decision.decision == "operator_review_required"
    assert any(
        "interacted with an access-control challenge" in reason
        for reason in decision.reasons
    )


def test_stealth_or_cookie_techniques_invalidate_origin_evidence() -> None:
    evidence = _origin(
        automation_techniques=("stealth_plugin", "cookie_import"),
    )

    decision = _evaluate(origin=evidence)

    assert decision.decision == "operator_review_required"
    assert any("cookie_import" in reason for reason in decision.reasons)
    assert any("stealth_plugin" in reason for reason in decision.reasons)


def test_parent_brand_host_without_full_entity_evidence_remains_unverified() -> None:
    evidence = _origin(observed_entity_tokens=("eon",))

    decision = _evaluate(origin=evidence)

    assert decision.decision == "operator_review_required"
    assert decision.origin_truth_state == "unverified"
    assert any("full distinctive employer entity" in reason for reason in decision.reasons)


def test_exact_url_relationship_is_required_not_merely_same_host() -> None:
    evidence = _origin(
        requested_url="https://www.eon.com/de/karriere",
        final_url="https://www.eon.com/de/karriere",
        canonical_url="https://www.eon.com/de/karriere",
    )

    decision = _evaluate(origin=evidence)

    assert decision.decision == "operator_review_required"
    assert any("does not exactly match" in reason for reason in decision.reasons)


def test_expired_origin_evidence_returns_to_review() -> None:
    evidence = _origin(expires_at="2026-08-04T09:30:00+00:00")

    decision = _evaluate(origin=evidence)

    assert decision.decision == "operator_review_required"
    assert any("expired" in reason for reason in decision.reasons)


def test_reachable_collector_proves_feasibility_but_not_activation() -> None:
    collector = _collector(
        status_code=200,
        reachable=True,
        challenge_detected=False,
        failure_class=None,
    )

    decision = _evaluate(collector=collector)

    assert decision.decision == "origin_verified_collection_ready"
    assert decision.collection_state == "ready"
    assert decision.collection_feasibility_proven is True
    assert decision.source_activation_allowed is False


def test_invalid_collector_provenance_cannot_claim_collection_ready() -> None:
    collector = _collector(
        status_code=200,
        reachable=True,
        challenge_detected=False,
        provider_requests=1,
    )

    decision = _evaluate(collector=collector)

    assert decision.decision == "origin_verified_collection_unknown"
    assert decision.collection_state == "unknown"
    assert decision.collection_feasibility_proven is False
    assert any("provider requests" in reason for reason in decision.reasons)


def test_replay_is_deterministic_and_network_free() -> None:
    first = _evaluate()
    second = _evaluate()

    assert first == second
    assert first.to_json() == second.to_json()
