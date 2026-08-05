from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Final, Mapping, Sequence

from src.search_intelligence.candidate_fact_authoring_pack import (
    WORKBOOK_SCHEMA,
    build_eon_authoring_workbook,
)
from src.search_intelligence.candidate_fact_profile import (
    CandidateFactProfile,
    load_candidate_fact_profile_json,
)


INTEGRITY_KEY: Final = "CANDIDATE-FACT-AUTHORING-INTEGRITY-001"
REPORT_SCHEMA: Final = "candidate_fact_authoring_integrity.v1"

DECISION_UNREVIEWED: Final = "unreviewed"
DECISION_EVIDENCE_AVAILABLE: Final = "evidence_available"
DECISION_NO_EVIDENCE: Final = "no_evidence"
DECISION_NOT_APPLICABLE: Final = "not_applicable"
DECISION_NEEDS_FOLLOWUP: Final = "needs_followup"

ALLOWED_DECISIONS: Final = frozenset(
    {
        DECISION_UNREVIEWED,
        DECISION_EVIDENCE_AVAILABLE,
        DECISION_NO_EVIDENCE,
        DECISION_NOT_APPLICABLE,
        DECISION_NEEDS_FOLLOWUP,
    }
)
FINAL_DECISIONS: Final = frozenset(
    {
        DECISION_EVIDENCE_AVAILABLE,
        DECISION_NO_EVIDENCE,
        DECISION_NOT_APPLICABLE,
    }
)

_WORKBOOK_KEYS: Final = frozenset(
    {
        "schema_version",
        "review_output_only_not_pipeline_input",
        "candidate_truth_state",
        "profile_version_target",
        "source_binding",
        "instructions",
        "requirements",
    }
)
_REQUIREMENT_KEYS: Final = frozenset(
    {
        "order",
        "statement_key",
        "employer_statement",
        "source_expectation_class",
        "obligation_strength",
        "canonical_employer_tags",
        "operator_review",
    }
)
_OPERATOR_REVIEW_KEYS: Final = frozenset(
    {"evidence_decision", "candidate_fact_keys", "private_notes"}
)
_ALLOWED_TRUTH_STATES: Final = frozenset(
    {"not_authored", "in_progress", "operator_reviewed"}
)


@dataclass(frozen=True)
class CandidateFactAuthoringIntegrity:
    integrity_key: str
    profile_version: str
    profile_status: str
    profile_payload_sha256: str
    workbook_sha256: str
    profile_fact_count: int
    requirement_count: int
    unique_employer_tag_count: int
    decision_counts: Mapping[str, int]
    distinct_referenced_fact_count: int
    all_references_exist: bool
    authoring_complete: bool
    blockers: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "integrity_key": self.integrity_key,
            "profile_version": self.profile_version,
            "profile_status": self.profile_status,
            "profile_payload_sha256": self.profile_payload_sha256,
            "workbook_sha256": self.workbook_sha256,
            "profile_fact_count": self.profile_fact_count,
            "requirement_count": self.requirement_count,
            "unique_employer_tag_count": self.unique_employer_tag_count,
            "decision_counts": dict(sorted(self.decision_counts.items())),
            "distinct_referenced_fact_count": self.distinct_referenced_fact_count,
            "all_references_exist": self.all_references_exist,
            "authoring_complete": self.authoring_complete,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class _WorkbookReview:
    decision: str
    candidate_fact_keys: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = set(value)
    missing = expected - actual
    extra = actual - expected
    if missing:
        raise ValueError(f"{label} is missing keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"{label} has unsupported keys: {sorted(extra)}")


def _required_string(value: object, label: str, *, maximum: int = 2000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    result = value.strip()
    if not result:
        raise ValueError(f"{label} must not be blank")
    if len(result) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return result


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = _required_string(raw, f"{label}[{index}]", maximum=128)
        _require(item not in seen, f"{label} contains duplicate Candidate Fact reference")
        seen.add(item)
        result.append(item)
    return tuple(result)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _parse_workbook_json(text: str) -> Mapping[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("private authoring workbook is not valid JSON") from exc
    workbook = _mapping(value, "authoring_workbook")
    _exact_keys(workbook, _WORKBOOK_KEYS, "authoring_workbook")
    return workbook


def _validate_invariant_workbook_fields(
    *,
    workbook: Mapping[str, Any],
    profile: CandidateFactProfile,
) -> Sequence[Mapping[str, Any]]:
    _require(
        workbook.get("schema_version") == WORKBOOK_SCHEMA,
        "unsupported private authoring workbook schema_version",
    )
    _require(
        workbook.get("review_output_only_not_pipeline_input") is True,
        "private authoring workbook must remain review-only",
    )
    truth_state = _required_string(
        workbook.get("candidate_truth_state"),
        "authoring_workbook.candidate_truth_state",
        maximum=64,
    )
    _require(
        truth_state in _ALLOWED_TRUTH_STATES,
        "private authoring workbook candidate_truth_state is unsupported",
    )
    _require(
        workbook.get("profile_version_target") == profile.profile_version,
        "private authoring workbook profile version does not match Candidate Fact profile",
    )

    expected = build_eon_authoring_workbook(profile_version=profile.profile_version)
    _require(
        workbook.get("source_binding") == expected["source_binding"],
        "private authoring workbook source binding drifted",
    )
    _require(
        workbook.get("instructions") == expected["instructions"],
        "private authoring workbook safety instructions drifted",
    )

    requirements = workbook.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError("authoring_workbook.requirements must be an array")
    _require(
        len(requirements) == len(expected["requirements"]) == 8,
        "private authoring workbook must contain exactly eight requirements",
    )
    return requirements


def _parse_review(
    *,
    requirement: Mapping[str, Any],
    expected_requirement: Mapping[str, Any],
    index: int,
    profile_fact_keys: frozenset[str],
) -> _WorkbookReview:
    label = f"authoring_workbook.requirements[{index}]"
    _exact_keys(requirement, _REQUIREMENT_KEYS, label)

    for key in (
        "order",
        "statement_key",
        "employer_statement",
        "source_expectation_class",
        "obligation_strength",
        "canonical_employer_tags",
    ):
        _require(
            requirement.get(key) == expected_requirement[key],
            f"{label}.{key} drifted from the sealed E.ON employer specification",
        )

    operator_review = _mapping(requirement.get("operator_review"), f"{label}.operator_review")
    _exact_keys(operator_review, _OPERATOR_REVIEW_KEYS, f"{label}.operator_review")

    decision = _required_string(
        operator_review.get("evidence_decision"),
        f"{label}.operator_review.evidence_decision",
        maximum=64,
    )
    _require(
        decision in ALLOWED_DECISIONS,
        f"{label}.operator_review.evidence_decision is unsupported",
    )

    fact_keys = _string_list(
        operator_review.get("candidate_fact_keys"),
        f"{label}.operator_review.candidate_fact_keys",
    )
    notes = operator_review.get("private_notes")
    _require(isinstance(notes, str), f"{label}.operator_review.private_notes must be a string")

    if decision == DECISION_EVIDENCE_AVAILABLE:
        _require(
            bool(fact_keys),
            f"{label} evidence_available requires at least one Candidate Fact reference",
        )
        unknown = tuple(key for key in fact_keys if key not in profile_fact_keys)
        _require(
            not unknown,
            f"{label} references Candidate Facts that do not exist in the private profile",
        )
    else:
        _require(
            not fact_keys,
            f"{label} non-evidence decision must not reference Candidate Facts",
        )

    return _WorkbookReview(decision=decision, candidate_fact_keys=fact_keys)


def validate_candidate_fact_authoring_integrity(
    *,
    profile_json: str,
    workbook_json: str,
) -> CandidateFactAuthoringIntegrity:
    profile = load_candidate_fact_profile_json(profile_json)
    workbook = _parse_workbook_json(workbook_json)
    requirements = _validate_invariant_workbook_fields(
        workbook=workbook,
        profile=profile,
    )
    expected = build_eon_authoring_workbook(profile_version=profile.profile_version)
    profile_fact_keys = frozenset(fact.fact_key for fact in profile.facts)

    reviews: list[_WorkbookReview] = []
    for index, (raw_requirement, expected_requirement) in enumerate(
        zip(requirements, expected["requirements"], strict=True)
    ):
        requirement = _mapping(
            raw_requirement,
            f"authoring_workbook.requirements[{index}]",
        )
        reviews.append(
            _parse_review(
                requirement=requirement,
                expected_requirement=expected_requirement,
                index=index,
                profile_fact_keys=profile_fact_keys,
            )
        )

    decision_counts = Counter(review.decision for review in reviews)
    referenced_keys = {
        key for review in reviews for key in review.candidate_fact_keys
    }
    unique_employer_tags = {
        tag
        for requirement in expected["requirements"]
        for tag in requirement["canonical_employer_tags"]
    }

    blockers: list[str] = []
    if decision_counts[DECISION_UNREVIEWED]:
        blockers.append("unreviewed_requirements_present")
    if decision_counts[DECISION_NEEDS_FOLLOWUP]:
        blockers.append("followup_requirements_present")

    all_final = all(review.decision in FINAL_DECISIONS for review in reviews)
    authoring_complete = all_final and not blockers

    return CandidateFactAuthoringIntegrity(
        integrity_key=INTEGRITY_KEY,
        profile_version=profile.profile_version,
        profile_status=profile.status,
        profile_payload_sha256=profile.payload_sha256,
        workbook_sha256=_canonical_sha256(workbook),
        profile_fact_count=len(profile.facts),
        requirement_count=len(reviews),
        unique_employer_tag_count=len(unique_employer_tags),
        decision_counts=dict(sorted(decision_counts.items())),
        distinct_referenced_fact_count=len(referenced_keys),
        all_references_exist=True,
        authoring_complete=authoring_complete,
        blockers=tuple(blockers),
    )
