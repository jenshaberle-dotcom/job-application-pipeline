from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from src.search_intelligence.candidate_fact_profile import parse_candidate_fact_profile
from src.search_intelligence.candidate_fact_profile_readiness import (
    absent_candidate_fact_profile_readiness,
    evaluate_candidate_fact_profile_readiness,
)


RUNNER = Path("scripts/run_candidate_fact_profile_readiness.py").read_text(
    encoding="utf-8"
)


def _approved_payload(
    *,
    status: str = "approved",
    capability_tags: list[str] | None = None,
    evidence_class: str = "portfolio_implementation",
) -> dict[str, object]:
    approved = status == "approved"
    fact_approved = approved
    return {
        "schema_version": "candidate_fact_profile.v1",
        "profile_key": "default",
        "profile_version": "private-v1",
        "status": status,
        "approved_by": "operator" if approved else None,
        "approved_at": "2026-08-05T12:00:00+02:00" if approved else None,
        "facts": [
            {
                "fact_key": "private.project.example",
                "category": "project",
                "evidence_class": evidence_class,
                "approval_status": "approved" if fact_approved else "proposed",
                "statement": "Private statement that must never enter readiness output.",
                "capability_tags": (
                    ["technology.python"]
                    if capability_tags is None
                    else capability_tags
                ),
                "limitations": [],
                "provenance": [
                    {
                        "source_type": "repository",
                        "reference": "private repository reference",
                        "observed_at": "2026-08-05T12:00:00+02:00",
                    }
                ],
                "valid_from": None,
                "valid_until": None,
                "approved_by": "operator" if fact_approved else None,
                "approved_at": (
                    "2026-08-05T12:00:00+02:00" if fact_approved else None
                ),
            }
        ],
    }


def _profile_row(payload: dict[str, object]) -> dict[str, object]:
    profile = parse_candidate_fact_profile(payload)
    return {
        "profile_key": profile.profile_key,
        "schema_version": profile.schema_version,
        "profile_version": profile.profile_version,
        "status": profile.status,
        "payload": profile.canonical_payload(),
        "payload_sha256": profile.payload_sha256,
        "source_type": "local_private_json",
        "approved_by": profile.approved_by,
        "approved_at": profile.approved_at,
    }


def _fact_rows(payload: dict[str, object]) -> tuple[dict[str, object], ...]:
    profile = parse_candidate_fact_profile(payload)
    return tuple(
        {
            "fact_key": fact.fact_key,
            "fact_payload": fact.canonical_payload(),
        }
        for fact in profile.facts
    )


def test_absent_profile_is_valid_not_ready_outcome() -> None:
    readiness = absent_candidate_fact_profile_readiness()

    assert readiness.profile_state == "absent"
    assert readiness.comparison_input_ready is False
    assert readiness.blockers == ("approved_profile_missing",)
    assert readiness.fact_count == 0


def test_valid_approved_profile_is_comparison_input_ready() -> None:
    payload = _approved_payload()
    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=_fact_rows(payload),
        revision_count=1,
    )

    assert readiness.profile_state == "approved"
    assert readiness.payload_valid is True
    assert readiness.payload_hash_matches is True
    assert readiness.normalized_rows_match is True
    assert readiness.approval_metadata_present is True
    assert readiness.fact_count == 1
    assert readiness.approved_fact_count == 1
    assert readiness.capability_evidence_fact_count == 1
    assert readiness.production_evidence_fact_count == 0
    assert readiness.distinct_capability_tag_count == 1
    assert readiness.blockers == ()
    assert readiness.comparison_input_ready is True


def test_draft_profile_remains_not_ready() -> None:
    payload = _approved_payload(status="draft")
    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=_fact_rows(payload),
        revision_count=0,
    )

    assert readiness.profile_state == "draft"
    assert readiness.comparison_input_ready is False
    assert "profile_not_approved" in readiness.blockers
    assert "approved_capability_evidence_missing" in readiness.blockers


def test_payload_hash_drift_fails_closed() -> None:
    payload = _approved_payload()
    row = _profile_row(payload)
    row["payload_sha256"] = "0" * 64

    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=row,
        fact_rows=_fact_rows(payload),
        revision_count=1,
    )

    assert readiness.payload_hash_matches is False
    assert "payload_hash_mismatch" in readiness.blockers
    assert readiness.comparison_input_ready is False


def test_normalized_fact_row_drift_fails_closed() -> None:
    payload = _approved_payload()
    rows = list(_fact_rows(payload))
    changed = deepcopy(rows[0])
    fact_payload = deepcopy(changed["fact_payload"])
    assert isinstance(fact_payload, dict)
    fact_payload["statement"] = "Changed persisted statement"
    changed["fact_payload"] = fact_payload

    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=(changed,),
        revision_count=1,
    )

    assert readiness.normalized_rows_match is False
    assert "normalized_fact_rows_mismatch" in readiness.blockers
    assert readiness.comparison_input_ready is False


def test_zero_capability_tags_remains_not_ready() -> None:
    payload = _approved_payload(capability_tags=[])
    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=_fact_rows(payload),
        revision_count=1,
    )

    assert readiness.capability_evidence_fact_count == 1
    assert readiness.distinct_capability_tag_count == 0
    assert "capability_tags_missing" in readiness.blockers
    assert readiness.comparison_input_ready is False


def test_non_capability_evidence_remains_not_ready() -> None:
    payload = _approved_payload(evidence_class="planned_capability")
    fact = payload["facts"][0]
    assert isinstance(fact, dict)
    fact["category"] = "project"
    fact["limitations"] = ["not_capability_evidence"]
    fact["provenance"] = [
        {
            "source_type": "operator_assertion",
            "reference": "private operator review",
            "observed_at": "2026-08-05T12:00:00+02:00",
        }
    ]

    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=_fact_rows(payload),
        revision_count=1,
    )

    assert readiness.capability_evidence_fact_count == 0
    assert "approved_capability_evidence_missing" in readiness.blockers
    assert readiness.comparison_input_ready is False


def test_missing_revision_history_fails_closed_for_approved_profile() -> None:
    payload = _approved_payload()
    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=_fact_rows(payload),
        revision_count=0,
    )

    assert "revision_history_missing" in readiness.blockers
    assert readiness.comparison_input_ready is False


def test_readiness_payload_is_redacted() -> None:
    payload = _approved_payload()
    readiness = evaluate_candidate_fact_profile_readiness(
        profile_row=_profile_row(payload),
        fact_rows=_fact_rows(payload),
        revision_count=1,
    )
    rendered = repr(readiness.canonical_payload())

    assert "Private statement" not in rendered
    assert "private repository reference" not in rendered
    assert "technology.python" not in rendered
    assert "private.project.example" not in rendered
    assert "operator" not in rendered


def test_runner_is_read_only_and_redacted() -> None:
    assert 'cur.execute("SET TRANSACTION READ ONLY")' in RUNNER
    assert "personal_statements_emitted" in RUNNER
    assert "provenance_references_emitted" in RUNNER
    assert "capability_tag_values_emitted" in RUNNER
    assert "fact_keys_emitted" in RUNNER
    assert "approver_identity_emitted" in RUNNER
    assert '"database_writes": 0' in RUNNER
    assert '"candidate_fact_writes": 0' in RUNNER
    assert '"capability_fit_decision_created": False' in RUNNER
    assert "INSERT INTO" not in RUNNER
    assert "UPDATE candidate_" not in RUNNER
    assert "DELETE FROM candidate_" not in RUNNER
    assert "eon_requirement_tag" not in RUNNER
