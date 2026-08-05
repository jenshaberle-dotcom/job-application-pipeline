from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.search_intelligence.candidate_fact_authoring_integrity import (
    DECISION_EVIDENCE_AVAILABLE,
    DECISION_NO_EVIDENCE,
    validate_candidate_fact_authoring_integrity,
)
from src.search_intelligence.candidate_fact_authoring_pack import (
    build_empty_draft_profile,
    build_eon_authoring_workbook,
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _empty_profile() -> dict[str, object]:
    return build_empty_draft_profile(profile_version="eon-authoring-draft-v1")


def _workbook() -> dict[str, object]:
    return build_eon_authoring_workbook(profile_version="eon-authoring-draft-v1")


def _profile_with_one_fact() -> dict[str, object]:
    profile = _empty_profile()
    profile["facts"] = [
        {
            "fact_key": "portfolio.python.pipeline",
            "category": "project",
            "evidence_class": "portfolio_implementation",
            "approval_status": "proposed",
            "statement": "Operator-authored private portfolio statement.",
            "capability_tags": ["technology.python"],
            "limitations": ["portfolio_not_professional_production"],
            "provenance": [
                {
                    "source_type": "repository",
                    "reference": "private repository reference",
                    "observed_at": "2026-08-05T12:00:00+00:00",
                }
            ],
            "valid_from": None,
            "valid_until": None,
            "approved_by": None,
            "approved_at": None,
        }
    ]
    return profile


def _set_all_decisions(workbook: dict[str, object], decision: str) -> None:
    requirements = workbook["requirements"]
    assert isinstance(requirements, list)
    for requirement in requirements:
        assert isinstance(requirement, dict)
        review = requirement["operator_review"]
        assert isinstance(review, dict)
        review["evidence_decision"] = decision
        review["candidate_fact_keys"] = []


def test_untouched_pack_is_valid_but_incomplete() -> None:
    result = validate_candidate_fact_authoring_integrity(
        profile_json=_json(_empty_profile()),
        workbook_json=_json(_workbook()),
    )

    assert result.profile_status == "draft"
    assert result.profile_fact_count == 0
    assert result.requirement_count == 8
    assert result.unique_employer_tag_count == 26
    assert result.decision_counts == {"unreviewed": 8}
    assert result.distinct_referenced_fact_count == 0
    assert result.all_references_exist is True
    assert result.authoring_complete is False
    assert result.blockers == ("unreviewed_requirements_present",)


def test_final_no_evidence_review_is_structurally_complete_without_fit() -> None:
    workbook = _workbook()
    _set_all_decisions(workbook, DECISION_NO_EVIDENCE)

    result = validate_candidate_fact_authoring_integrity(
        profile_json=_json(_empty_profile()),
        workbook_json=_json(workbook),
    )

    assert result.decision_counts == {"no_evidence": 8}
    assert result.authoring_complete is True
    assert result.blockers == ()
    payload = result.canonical_payload()
    assert "statement" not in json.dumps(payload)
    assert "provenance" not in json.dumps(payload)
    assert "technology.python" not in json.dumps(payload)
    assert "portfolio.python.pipeline" not in json.dumps(payload)


def test_evidence_available_requires_existing_private_fact_reference() -> None:
    workbook = _workbook()
    _set_all_decisions(workbook, DECISION_NO_EVIDENCE)
    requirements = workbook["requirements"]
    assert isinstance(requirements, list)
    first = requirements[0]
    assert isinstance(first, dict)
    review = first["operator_review"]
    assert isinstance(review, dict)
    review["evidence_decision"] = DECISION_EVIDENCE_AVAILABLE
    review["candidate_fact_keys"] = ["portfolio.python.pipeline"]

    result = validate_candidate_fact_authoring_integrity(
        profile_json=_json(_profile_with_one_fact()),
        workbook_json=_json(workbook),
    )

    assert result.profile_fact_count == 1
    assert result.distinct_referenced_fact_count == 1
    assert result.all_references_exist is True
    assert result.authoring_complete is True


def test_unknown_candidate_fact_reference_fails_closed() -> None:
    workbook = _workbook()
    requirements = workbook["requirements"]
    assert isinstance(requirements, list)
    first = requirements[0]
    assert isinstance(first, dict)
    review = first["operator_review"]
    assert isinstance(review, dict)
    review["evidence_decision"] = DECISION_EVIDENCE_AVAILABLE
    review["candidate_fact_keys"] = ["missing.private.fact"]

    with pytest.raises(ValueError, match="do not exist"):
        validate_candidate_fact_authoring_integrity(
            profile_json=_json(_empty_profile()),
            workbook_json=_json(workbook),
        )


def test_non_evidence_decision_cannot_reference_candidate_fact() -> None:
    workbook = _workbook()
    requirements = workbook["requirements"]
    assert isinstance(requirements, list)
    first = requirements[0]
    assert isinstance(first, dict)
    review = first["operator_review"]
    assert isinstance(review, dict)
    review["evidence_decision"] = DECISION_NO_EVIDENCE
    review["candidate_fact_keys"] = ["portfolio.python.pipeline"]

    with pytest.raises(ValueError, match="must not reference"):
        validate_candidate_fact_authoring_integrity(
            profile_json=_json(_profile_with_one_fact()),
            workbook_json=_json(workbook),
        )


def test_duplicate_candidate_fact_reference_fails_closed() -> None:
    workbook = _workbook()
    requirements = workbook["requirements"]
    assert isinstance(requirements, list)
    first = requirements[0]
    assert isinstance(first, dict)
    review = first["operator_review"]
    assert isinstance(review, dict)
    review["evidence_decision"] = DECISION_EVIDENCE_AVAILABLE
    review["candidate_fact_keys"] = [
        "portfolio.python.pipeline",
        "portfolio.python.pipeline",
    ]

    with pytest.raises(ValueError, match="duplicate Candidate Fact reference"):
        validate_candidate_fact_authoring_integrity(
            profile_json=_json(_profile_with_one_fact()),
            workbook_json=_json(workbook),
        )


def test_source_binding_drift_fails_closed() -> None:
    workbook = _workbook()
    source_binding = workbook["source_binding"]
    assert isinstance(source_binding, dict)
    source_binding["tag_map_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="source binding drifted"):
        validate_candidate_fact_authoring_integrity(
            profile_json=_json(_empty_profile()),
            workbook_json=_json(workbook),
        )


def test_requirement_or_tag_drift_fails_closed() -> None:
    workbook = _workbook()
    requirements = workbook["requirements"]
    assert isinstance(requirements, list)
    first = requirements[0]
    assert isinstance(first, dict)
    tags = first["canonical_employer_tags"]
    assert isinstance(tags, list)
    tags.append("invented.candidate.truth")

    with pytest.raises(ValueError, match="sealed E.ON employer specification"):
        validate_candidate_fact_authoring_integrity(
            profile_json=_json(_empty_profile()),
            workbook_json=_json(workbook),
        )


def test_profile_version_mismatch_fails_closed() -> None:
    workbook = _workbook()
    workbook["profile_version_target"] = "different-version"

    with pytest.raises(ValueError, match="profile version does not match"):
        validate_candidate_fact_authoring_integrity(
            profile_json=_json(_empty_profile()),
            workbook_json=_json(workbook),
        )


def test_validator_does_not_mutate_inputs() -> None:
    profile = _profile_with_one_fact()
    workbook = _workbook()
    original_profile = copy.deepcopy(profile)
    original_workbook = copy.deepcopy(workbook)

    validate_candidate_fact_authoring_integrity(
        profile_json=_json(profile),
        workbook_json=_json(workbook),
    )

    assert profile == original_profile
    assert workbook == original_workbook


def test_runner_has_no_database_network_import_or_fit_authority() -> None:
    source = Path("scripts/run_private_candidate_fact_authoring_integrity.py").read_text(
        encoding="utf-8"
    ).casefold()

    assert "psycopg" not in source
    assert "import requests" not in source
    assert "from requests" not in source
    assert "--apply" not in source
    assert "approval-token" not in source
    assert "insert into" not in source
    assert "update " not in source
    assert "delete from" not in source
    assert '"capability_fit_decision_created": false' in source
    assert '"semantic_requirement_comparison_created": false' in source
    assert '"candidate_fact_keys_emitted": false' in source
