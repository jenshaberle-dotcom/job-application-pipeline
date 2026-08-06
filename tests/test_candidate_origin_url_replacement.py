from __future__ import annotations

from pathlib import Path

import pytest

from src.search_intelligence.candidate_origin_url_replacement import (
    APPROVAL_TOKEN,
    CandidateOriginSnapshot,
    ReplacementRequest,
    build_replacement_plan_item,
    canonical_https_url,
    classify_apply_set,
    parse_repair_spec,
    same_url,
    validate_apply_authority,
    validate_unique_requests,
)
from src.search_intelligence.connector_feasibility import (
    ConnectorFeasibilityItem,
    EvidenceClassification,
    OriginCandidate,
    UrlQualityFeedback,
)


MIGRATION = Path(
    "db/migrations/089_add_candidate_origin_url_replacement_decision.sql"
).read_text(encoding="utf-8")
RUNNER = Path(
    "scripts/run_candidate_origin_url_replacement.py"
).read_text(encoding="utf-8")


def request(
    *,
    candidate_id: int = 57,
    company_key: str = "accompio",
    previous_url: str = "https://www.example.com/career/",
    proposed_url: str = "https://jobs.example.com/de",
) -> ReplacementRequest:
    return ReplacementRequest(
        candidate_id=candidate_id,
        company_key=company_key,
        expected_previous_url=previous_url,
        proposed_url=proposed_url,
    )


def candidate(
    *,
    candidate_id: int = 57,
    company_key: str = "accompio",
    status: str = "discovery",
    candidate_url: str | None = "https://www.example.com/career/",
) -> CandidateOriginSnapshot:
    return CandidateOriginSnapshot(
        candidate_id=candidate_id,
        company_key=company_key,
        company_name="Example GmbH",
        status=status,
        candidate_url=candidate_url,
        source_name_candidate="example",
        risk_level="low",
    )


def feasibility(
    *,
    repair_url: str | None = "https://jobs.example.com/de",
    blocker_code: str | None = "origin_url_repair_candidate_detected",
) -> ConnectorFeasibilityItem:
    origin = OriginCandidate(
        candidate_id=57,
        company_key="accompio",
        company_name="Example GmbH",
        origin_url="https://www.example.com/career/",
    )
    feedback = UrlQualityFeedback(
        status="repair_candidate_detected" if repair_url else "not_evaluated",
        code="trusted_delegated_job_board_detected" if repair_url else None,
        repair_candidate_url=repair_url,
        message="test",
    )
    return ConnectorFeasibilityItem(
        candidate=origin,
        http_status=200,
        reachable=True,
        page_type="career_search_or_job_board",
        sample_job_urls=(),
        structural_job_evidence_count=0,
        feasibility_status="manual_review_required",
        decision="manual_review_required",
        blocker_code=blocker_code,
        reason="test evidence",
        recommended_next_action="review",
        url_quality=feedback,
        evidence_classification=EvidenceClassification((), ()),
        evidence={},
    )


def test_parse_repair_spec_and_conservative_url_equality() -> None:
    parsed = parse_repair_spec(
        "57:accompio|https://www.example.com/career/|https://jobs.example.com/de/"
    )

    assert parsed.target == "57:accompio"
    assert parsed.proposed_url == "https://jobs.example.com/de/"
    assert same_url(
        "https://JOBS.example.com/de/",
        "https://jobs.example.com/de",
    )
    assert canonical_https_url("http://jobs.example.com/de") is None
    assert canonical_https_url("https://jobs.example.com/de#fragment") is None


def test_exact_live_repair_candidate_is_replacement_ready() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(),
        feasibility(),
    )

    assert plan.decision == "replace_validated_candidate_url"
    assert plan.status == "operator_decision_required"
    assert plan.apply_allowed is True
    assert classify_apply_set([plan]) == "apply_ready"


def test_mismatched_live_repair_candidate_fails_closed() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(),
        feasibility(repair_url="https://jobs.example.com/search"),
    )

    assert plan.decision == "live_repair_candidate_mismatch"
    assert plan.status == "valid_stop"
    assert plan.apply_allowed is False


def test_missing_live_repair_outcome_fails_closed() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(),
        feasibility(
            repair_url=None,
            blocker_code="structural_evidence_without_job_detail",
        ),
    )

    assert plan.decision == "live_repair_evidence_missing"
    assert plan.apply_allowed is False


def test_previous_url_drift_fails_closed() -> None:
    plan = build_replacement_plan_item(
        request(previous_url="https://www.example.com/other"),
        candidate(),
        feasibility(),
    )

    assert plan.decision == "previous_url_drift"
    assert plan.apply_allowed is False


def test_candidate_key_mismatch_fails_closed() -> None:
    plan = build_replacement_plan_item(
        request(company_key="expected"),
        candidate(company_key="actual"),
        feasibility(),
    )

    assert plan.decision == "target_identity_mismatch"
    assert plan.apply_allowed is False


def test_active_controlled_candidate_is_protected() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(status="active_controlled"),
        feasibility(),
    )

    assert plan.decision == "protected_active_controlled"
    assert plan.apply_allowed is False


def test_duplicate_selected_url_fails_closed() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(),
        feasibility(),
        duplicate_selected_url_exists=True,
    )

    assert plan.decision == "duplicate_selected_url"
    assert plan.apply_allowed is False


def test_already_replaced_is_idempotent_even_after_expected_old_url() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(candidate_url="https://jobs.example.com/de/"),
        feasibility(),
    )

    assert plan.decision == "no_action_already_replaced"
    assert plan.status == "passed"
    assert plan.apply_allowed is False
    assert classify_apply_set([plan]) == "idempotent_replay"


def test_initial_persistence_remains_owned_by_cand001() -> None:
    plan = build_replacement_plan_item(
        request(),
        candidate(candidate_url=None),
        feasibility(),
    )

    assert plan.decision == "initial_persistence_required"
    assert plan.apply_allowed is False


def test_apply_requires_exact_token_and_complete_target_coverage() -> None:
    requests = validate_unique_requests(
        [
            request(),
            request(
                candidate_id=23,
                company_key="computacenter",
                previous_url="https://jobs.example.org/",
                proposed_url="https://jobs.example.org/search/",
            ),
        ]
    )

    with pytest.raises(ValueError, match="approval token"):
        validate_apply_authority(
            requests,
            approval_token="wrong",
            approved_targets=[item.target for item in requests],
        )

    with pytest.raises(ValueError, match="coverage"):
        validate_apply_authority(
            requests,
            approval_token=APPROVAL_TOKEN,
            approved_targets=["57:accompio"],
        )

    validate_apply_authority(
        requests,
        approval_token=APPROVAL_TOKEN,
        approved_targets=[item.target for item in requests],
    )


def test_duplicate_targets_are_rejected() -> None:
    duplicate = request()
    with pytest.raises(ValueError, match="Duplicate repair target"):
        validate_unique_requests([duplicate, duplicate])


def test_migration_extends_existing_audit_contract() -> None:
    assert (
        "089_add_candidate_origin_url_replacement_decision.sql"
        in "db/migrations/089_add_candidate_origin_url_replacement_decision.sql"
    )
    assert "candidate_origin_url_persistence_reviews" in MIGRATION
    assert (
        "DROP CONSTRAINT IF EXISTS chk_candidate_origin_url_persistence_decision"
        in MIGRATION
    )
    assert "'replace_validated_candidate_url'::text" in MIGRATION
    assert (
        "CREATE OR REPLACE VIEW gold_candidate_origin_url_persistence_review_history"
        in MIGRATION
    )


def test_runner_keeps_exact_atomic_and_no_provider_boundaries() -> None:
    assert "FOR UPDATE" in RUNNER
    assert "candidate_url = %s" in RUNNER
    assert "company_key = %s" in RUNNER
    assert "status <> 'active_controlled'" in RUNNER
    assert "replace_validated_candidate_url" in RUNNER
    assert "live_s7n_repair_candidate" in RUNNER
    assert "provider_requests" in RUNNER
    assert '"provider_requests": 0' in RUNNER
    assert '"llm_requests": 0' in RUNNER
    assert "run_origin_url_default_repair" not in RUNNER
    assert "tavily" not in RUNNER.lower()
    assert "openai" not in RUNNER.lower()
