from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.run_f5_application_lifecycle_reconciliation import (
    ReconciliationStop,
    reconcile,
)


OBSERVED_AT = datetime(2026, 9, 16, 17, 0, tzinfo=timezone.utc)
SOURCE_SHA = "a" * 40


def _surface(**overrides: object) -> dict[str, object]:
    surface: dict[str, object] = {
        "applications_surface_present": True,
        "static_no_submitted_copy_present": True,
        "manual_submission_boundary_present": True,
        "future_interview_copy_present": True,
        "future_decision_copy_present": True,
        "product_payload_has_application_portfolio_field": False,
    }
    surface.update(overrides)
    return surface


def _snapshot(
    *,
    draft_status_counts: dict[str, int] | None = None,
    extra_relations: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    relations: list[dict[str, object]] = [
        {
            "name": "application_source_documents",
            "kind": "r",
            "columns": ["id", "document_type", "status"],
            "constraints": [],
        },
        {
            "name": "application_draft_requests",
            "kind": "r",
            "columns": ["id", "silver_job_id", "status", "created_at", "updated_at"],
            "constraints": [],
        },
        {
            "name": "gold_product_v1_application_readiness",
            "kind": "v",
            "columns": ["silver_job_id", "application_readiness_status"],
            "constraints": [],
        },
    ]
    relations.extend(extra_relations or [])
    counts = draft_status_counts or {
        "drafted_for_review": 2,
        "approved_by_operator": 1,
    }
    return {
        "relations": relations,
        "source_documents": {
            "present": True,
            "row_count": 2,
            "status_counts": {"approved": 2},
            "document_type_counts": {"base_cv": 1, "base_application_letter": 1},
        },
        "draft_requests": {
            "present": True,
            "row_count": sum(counts.values()),
            "distinct_job_count": 2,
            "status_counts": counts,
            "latest_created_at": "2026-09-16T10:00:00+00:00",
            "latest_updated_at": "2026-09-16T10:00:00+00:00",
        },
        "application_readiness": {"present": True, "row_count": 70},
    }


def test_draft_and_operator_approval_never_become_submission_authority() -> None:
    report = reconcile(
        _snapshot(),
        source_sha=SOURCE_SHA,
        observed_at=OBSERVED_AT,
        surface_evidence=_surface(),
    )

    summary = report["summary"]
    findings = report["authority_findings"]
    assert summary["application_draft_request_count"] == 3
    assert summary["operator_approved_draft_count"] == 1
    assert summary["submitted_like_draft_status_count"] == 0
    assert findings["draft_request_is_submission_authority"] is False
    assert findings["draft_or_operator_approval_implies_submitted"] is False
    assert findings["current_ui_may_invent_submitted_application"] is False


def test_submitted_like_legacy_status_is_measured_but_not_promoted_to_authority() -> None:
    report = reconcile(
        _snapshot(draft_status_counts={"submitted": 2, "approved_by_operator": 1}),
        source_sha=SOURCE_SHA,
        observed_at=OBSERVED_AT,
        surface_evidence=_surface(),
    )

    assert report["summary"]["submitted_like_draft_status_count"] == 2
    assert report["authority_findings"]["draft_request_is_submission_authority"] is False
    assert report["authority_findings"]["current_f5_contract_defines_submission_authority_store"] is False


def test_post_submit_named_relation_is_candidate_evidence_only() -> None:
    report = reconcile(
        _snapshot(
            extra_relations=[
                {
                    "name": "application_response_events_legacy",
                    "kind": "r",
                    "columns": ["id", "payload"],
                    "constraints": [],
                }
            ]
        ),
        source_sha=SOURCE_SHA,
        observed_at=OBSERVED_AT,
        surface_evidence=_surface(),
    )

    assert report["post_submit_candidate_relations"] == [
        "application_response_events_legacy"
    ]
    assert report["summary"]["post_submit_candidate_relation_count"] == 1
    assert report["authority_findings"]["relation_name_alone_creates_lifecycle_authority"] is False


def test_surface_portfolio_projection_is_reported_separately_from_db_authority() -> None:
    report = reconcile(
        _snapshot(),
        source_sha=SOURCE_SHA,
        observed_at=OBSERVED_AT,
        surface_evidence=_surface(product_payload_has_application_portfolio_field=True),
    )

    assert report["summary"]["persisted_application_portfolio_projected_to_ui"] is True
    assert report["authority_findings"]["current_f5_contract_defines_submission_authority_store"] is False


def test_zero_side_effect_boundary_is_explicit() -> None:
    report = reconcile(
        _snapshot(),
        source_sha=SOURCE_SHA,
        observed_at=OBSERVED_AT,
        surface_evidence=_surface(),
    )

    assert report["boundaries"] == {
        "db_writes": 0,
        "provider_calls": 0,
        "network_probes": 0,
        "gmail_reads": 0,
        "email_actions": 0,
        "application_submission_actions": 0,
        "application_state_mutations": 0,
        "ranking_authority_changed": False,
        "top5_authority_changed": False,
    }


def test_invalid_relation_shape_fails_closed() -> None:
    snapshot = _snapshot()
    snapshot["relations"] = "not-a-sequence"

    with pytest.raises(ReconciliationStop, match="RELATIONS_INVALID"):
        reconcile(
            snapshot,
            source_sha=SOURCE_SHA,
            observed_at=OBSERVED_AT,
            surface_evidence=_surface(),
        )
