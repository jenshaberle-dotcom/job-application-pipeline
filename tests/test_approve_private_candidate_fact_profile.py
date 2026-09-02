from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.approve_private_candidate_fact_profile import build_approved_payload
from src.search_intelligence.candidate_fact_profile import load_candidate_fact_profile_json


def _draft() -> dict[str, object]:
    return {
        "schema_version": "candidate_fact_profile.v1",
        "profile_key": "default",
        "profile_version": "demo-private-v1",
        "status": "draft",
        "approved_by": None,
        "approved_at": None,
        "facts": [
            {
                "fact_key": "employment.example.systems",
                "category": "skill",
                "evidence_class": "professional_employment",
                "approval_status": "proposed",
                "statement": "Reviewed systems engineering evidence.",
                "capability_tags": ["systems-engineering"],
                "limitations": [],
                "provenance": [
                    {
                        "source_type": "canonical_cv",
                        "reference": "private/current-cv.pdf",
                        "observed_at": "2026-09-02T14:00:00+00:00",
                    }
                ],
                "valid_from": None,
                "valid_until": None,
                "approved_by": None,
                "approved_at": None,
            },
            {
                "fact_key": "target.example.ai",
                "category": "target_direction",
                "evidence_class": "target_direction",
                "approval_status": "proposed",
                "statement": "Reviewed target direction.",
                "capability_tags": ["ai-engineering"],
                "limitations": ["not_capability_evidence"],
                "provenance": [
                    {
                        "source_type": "operator_assertion",
                        "reference": "private operator review",
                        "observed_at": "2026-09-02T14:00:00+00:00",
                    }
                ],
                "valid_from": None,
                "valid_until": None,
                "approved_by": None,
                "approved_at": None,
            },
        ],
    }


def test_approval_changes_only_status_and_approval_metadata() -> None:
    draft = _draft()
    before = deepcopy(draft)
    approved = build_approved_payload(
        draft,
        approved_by="jens",
        approved_at="2026-09-02T14:30:00+00:00",
    )

    assert approved["status"] == "approved"
    assert approved["approved_by"] == "jens"
    assert approved["approved_at"] == "2026-09-02T14:30:00+00:00"
    assert draft == before
    assert len(approved["facts"]) == 2
    for old, new in zip(draft["facts"], approved["facts"], strict=True):
        assert new["approval_status"] == "approved"
        assert new["approved_by"] == "jens"
        assert new["approved_at"] == "2026-09-02T14:30:00+00:00"
        for key in (
            "fact_key",
            "category",
            "evidence_class",
            "statement",
            "capability_tags",
            "limitations",
            "provenance",
            "valid_from",
            "valid_until",
        ):
            assert new[key] == old[key]

    parsed = load_candidate_fact_profile_json(__import__("json").dumps(approved))
    assert parsed.status == "approved"
    assert len(parsed.approved_facts) == 2
    assert len(parsed.capability_evidence_facts) == 1


def test_batch_approval_refuses_non_proposed_fact() -> None:
    draft = _draft()
    draft["facts"][0]["approval_status"] = "rejected"
    with pytest.raises(RuntimeError, match="must be proposed"):
        build_approved_payload(
            draft,
            approved_by="jens",
            approved_at="2026-09-02T14:30:00+00:00",
        )


def test_target_direction_remains_non_capability_evidence() -> None:
    approved = build_approved_payload(
        _draft(),
        approved_by="jens",
        approved_at="2026-09-02T14:30:00+00:00",
    )
    parsed = load_candidate_fact_profile_json(__import__("json").dumps(approved))
    assert [fact.fact_key for fact in parsed.capability_evidence_facts] == [
        "employment.example.systems"
    ]
